"""NVIDIA Parakeet-EOU-120M INT8 ONNX Streaming Speech Recognition Engine.

Features:
- Cache-aware FastConformer RNN-T streaming inference
- Instant End-of-Utterance (<EOU>) turn boundary detection
- Sub-50ms latency on CPU
"""

import os
import json
import numpy as np
import onnxruntime as ort
from typing import Optional, Tuple, List, Generator, Callable


def _slaney_mel_filterbank(n_fft: int = 512, n_mels: int = 128, sr: int = 16000) -> np.ndarray:
    """Precompute Slaney-scale, Slaney-normalized mel filterbank."""
    f_sp = 200.0 / 3.0
    min_log_hz, log_step = 1000.0, np.log(6.4) / 27.0
    min_log_mel = min_log_hz / f_sp

    def hz_to_mel(hz):
        hz = np.asarray(hz, dtype=np.float64)
        safe_hz = np.maximum(hz, 1e-12)
        return np.where(hz >= min_log_hz, min_log_mel + np.log(safe_hz / min_log_hz) / log_step, hz / f_sp)

    def mel_to_hz(mel):
        mel = np.asarray(mel, dtype=np.float64)
        return np.where(mel >= min_log_mel, min_log_hz * np.exp(log_step * (mel - min_log_mel)), f_sp * mel)

    mel_pts = mel_to_hz(np.linspace(hz_to_mel(0.0), hz_to_mel(sr / 2.0), n_mels + 2))
    fft_freqs = np.arange(n_fft // 2 + 1) * sr / n_fft
    fb = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
    for m in range(n_mels):
        f_l, f_c, f_r = mel_pts[m], mel_pts[m + 1], mel_pts[m + 2]
        norm = 2.0 / (f_r - f_l)
        rising = (fft_freqs >= f_l) & (fft_freqs < f_c)
        falling = (fft_freqs >= f_c) & (fft_freqs <= f_r)
        fb[m, rising] = norm * (fft_freqs[rising] - f_l) / (f_c - f_l)
        fb[m, falling] = norm * (f_r - fft_freqs[falling]) / (f_r - f_c)
    return fb


_MEL_FB = _slaney_mel_filterbank(512, 128, 16000)
_HANN = (0.5 * (1.0 - np.cos(2.0 * np.pi * np.arange(400) / 399.0))).astype(np.float32)


def compute_mel_spectrogram(samples: np.ndarray) -> np.ndarray:
    """Compute 128-bin log-mel spectrogram for 16kHz audio."""
    n_fft, hop, win, preemph = 512, 160, 400, 0.97
    pad = n_fft // 2
    if len(samples) < 2:
        return np.zeros((128, 0), dtype=np.float32)

    x = np.concatenate([[samples[0]], samples[1:] - preemph * samples[:-1]]).astype(np.float32)
    x = np.pad(x, (pad, pad))
    n_frames = max(1, 1 + (len(x) - win) // hop)
    off = (n_fft - win) // 2
    frames = np.zeros((n_frames, n_fft), dtype=np.float32)
    for i in range(n_frames):
        start = i * hop + off
        seg = x[start: start + win]
        frames[i, off: off + len(seg)] = seg * _HANN[: len(seg)]
    spec = np.abs(np.fft.rfft(frames, n=n_fft, axis=1)) ** 2
    mel = spec.astype(np.float32) @ _MEL_FB.T
    mel = np.log(np.maximum(mel, 1e-12) + 2.0 ** -24)
    return mel.T  # [128, n_frames]


def trim_trailing_silence(audio: np.ndarray, threshold: float = 0.012, min_keep: int = 8000) -> np.ndarray:
    """Trim trailing dead silence chunks from audio to minimize decode frames."""
    if len(audio) <= min_keep:
        return audio
    chunk_size = 320  # 20ms at 16kHz
    n = len(audio) // chunk_size
    last_voice = n
    for i in range(n - 1, -1, -1):
        seg = audio[i * chunk_size : (i + 1) * chunk_size]
        if np.abs(seg).mean() > threshold:
            last_voice = min(n, i + 3)  # keep 60ms cushion
            break
    end_idx = max(min_keep, last_voice * chunk_size)
    return audio[:end_idx]


class ParakeetEOU:
    """Parakeet-EOU-120M INT8 ONNX Model."""

    BLANK_ID = 1026
    EOU_ID = 1024
    EOB_ID = 1025
    MAX_SYMBOLS_PER_FRAME = 2

    @staticmethod
    def find_model_dir() -> Optional[str]:
        candidates = [
            os.path.join(os.path.dirname(__file__), "models", "parakeet-eou-120m"),
            os.path.join(os.getcwd(), "models", "parakeet-eou-120m"),
            r"C:\WORk\Jarvis-ai\jarvis\models\parakeet-eou-120m",
            os.path.expanduser(r"~\.cache\parakeet-eou-120m")
        ]
        for c in candidates:
            if os.path.exists(os.path.join(c, "parakeet-eou-encoder.onnx")):
                return c
        return None

    def __init__(self, model_dir: Optional[str] = None):
        if not model_dir:
            model_dir = self.find_model_dir()
            if not model_dir:
                raise FileNotFoundError("Parakeet-EOU model directory not found. Please run download_parakeet.py to fetch the models.")
        self.model_dir = model_dir
        enc_path = os.path.join(model_dir, "parakeet-eou-encoder.onnx")
        dec_path = os.path.join(model_dir, "parakeet-eou-decoder.onnx")
        jnt_path = os.path.join(model_dir, "parakeet-eou-joint.onnx")
        vocab_path = os.path.join(model_dir, "vocab.json")

        if not os.path.exists(enc_path):
            raise FileNotFoundError(f"Missing model file: {enc_path}. Run download_parakeet.py to install.")

        sess_opts = ort.SessionOptions()
        sess_opts.intra_op_num_threads = 4
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self.enc = ort.InferenceSession(enc_path, sess_opts, providers=["CPUExecutionProvider"])
        self.dec = ort.InferenceSession(dec_path, sess_opts, providers=["CPUExecutionProvider"])
        self.jnt = ort.InferenceSession(jnt_path, sess_opts, providers=["CPUExecutionProvider"])

        with open(vocab_path, "r", encoding="utf-8") as f:
            self.vocab = json.load(f)

        self.reset()

    def reset(self):
        """Reset internal streaming state."""
        self.pre_cache = np.zeros((1, 128, 9), dtype=np.float32)
        self.cache_ch = np.zeros((17, 1, 70, 512), dtype=np.float32)
        self.cache_tm = np.zeros((17, 1, 512, 8), dtype=np.float32)
        self.cache_len = np.zeros((1,), dtype=np.int64)

        self.h = np.zeros((1, 1, 640), dtype=np.float32)
        self.c = np.zeros((1, 1, 640), dtype=np.float32)
        self.last_token = self.BLANK_ID

        # Initial forward pass through decoder with blank token
        self.dec_out, self.h, self.c = self.dec.run(
            None,
            {"token": np.array([[self.last_token]], dtype=np.int64), "h": self.h, "c": self.c}
        )

    def decode_chunk(self, mel_window_64: np.ndarray) -> Tuple[List[str], bool]:
        """Decode a 64-frame mel spectrogram window.
        
        Returns:
            emitted_pieces: list of word piece strings emitted in this step
            eou_detected: True if End-of-Utterance (<EOU>) was encountered
        """
        mel_input = np.expand_dims(mel_window_64, 0).astype(np.float32)
        out = self.enc.run(None, {
            "audio_signal": mel_input,
            "audio_length": np.array([64], dtype=np.int64),
            "pre_cache": self.pre_cache,
            "cache_last_channel": self.cache_ch,
            "cache_last_time": self.cache_tm,
            "cache_last_channel_len": self.cache_len,
        })
        encoded, enc_len, self.pre_cache, self.cache_ch, self.cache_tm, self.cache_len = out
        self.cache_len = self.cache_len.astype(np.int64)

        emitted_pieces = []
        eou_detected = False

        # Output frames: last 4 frames represent the new chunk's output
        for t in range(4, 8):
            enc_frame = encoded[:, t:t+1, :]
            symbols = 0
            while symbols < self.MAX_SYMBOLS_PER_FRAME:
                j_out = self.jnt.run(None, {"encoder_output": enc_frame, "decoder_output": self.dec_out})
                pred_tok = int(np.argmax(j_out[0][0, 0]))

                if pred_tok == self.BLANK_ID or pred_tok == self.EOB_ID:
                    break
                if pred_tok == self.EOU_ID:
                    eou_detected = True
                    break

                piece = self.vocab.get(str(pred_tok), "")
                emitted_pieces.append(piece)
                self.last_token = pred_tok
                self.dec_out, self.h, self.c = self.dec.run(
                    None,
                    {"token": np.array([[self.last_token]], dtype=np.int64), "h": self.h, "c": self.c}
                )
                symbols += 1

            if eou_detected:
                break

        return emitted_pieces, eou_detected

    def transcribe(self, audio_samples: np.ndarray, on_partial: Optional[Callable[[str], None]] = None) -> str:
        """Transcribe complete audio array (16kHz float32 or int16) with streaming step."""
        if audio_samples.dtype == np.int16:
            audio_samples = audio_samples.astype(np.float32) / 32768.0

        audio_samples = trim_trailing_silence(audio_samples)
        self.reset()
        full_mel = compute_mel_spectrogram(audio_samples)
        total_frames = full_mel.shape[1]

        step_frames = 32
        window_frames = 64
        all_pieces = []

        for start in range(0, total_frames - window_frames + 1, step_frames):
            chunk = full_mel[:, start:start+window_frames]
            pieces, eou = self.decode_chunk(chunk)
            if pieces:
                all_pieces.extend(pieces)
                if on_partial:
                    text = "".join(all_pieces).replace("\u2581", " ").strip()
                    on_partial(text)
            if eou and len(all_pieces) > 2:
                # EOU detected after some speech
                break

        text = "".join(all_pieces).replace("\u2581", " ").strip()
        return text


class ParakeetTDT:
    """NVIDIA Parakeet-TDT 0.6B (622MB) via sherpa-onnx.
    Token-and-duration transducer with sub-300ms inference and full punctuation.
    """
    def __init__(self, model_dir: Optional[str] = None):
        import sherpa_onnx
        if not model_dir:
            candidates = [
                os.path.join(os.path.expanduser("~"), ".cache", "openwhispr", "parakeet-models", "parakeet-tdt-0.6b-v3"),
                os.path.join(os.path.dirname(__file__), "models", "parakeet-tdt-0.6b-v3"),
                os.path.join(os.getcwd(), "models", "parakeet-tdt-0.6b-v3"),
            ]
            for c in candidates:
                if os.path.exists(os.path.join(c, "encoder.int8.onnx")):
                    model_dir = c
                    break
        if not model_dir or not os.path.exists(os.path.join(model_dir, "encoder.int8.onnx")):
            raise FileNotFoundError(f"Parakeet-TDT model directory not found: {model_dir}")

        self.model_dir = model_dir
        self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=os.path.join(model_dir, "encoder.int8.onnx"),
            decoder=os.path.join(model_dir, "decoder.int8.onnx"),
            joiner=os.path.join(model_dir, "joiner.int8.onnx"),
            tokens=os.path.join(model_dir, "tokens.txt"),
            num_threads=4,
            sample_rate=16000,
            feature_dim=80,
            model_type="nemo_transducer",
            provider="cpu"
        )

    def transcribe(self, audio_samples: np.ndarray, on_partial: Optional[Callable[[str], None]] = None) -> str:
        """Transcribes complete audio array (float32 or int16, 16kHz)."""
        if audio_samples.dtype == np.int16:
            audio_samples = audio_samples.astype(np.float32) / 32768.0

        stream = self.recognizer.create_stream()
        stream.accept_waveform(16000, audio_samples)
        self.recognizer.decode_stream(stream)
        text = stream.result.text.strip()
        if on_partial and text:
            on_partial(text)
        return text


def get_best_stt_engine():
    """Discovers and returns the NVIDIA Parakeet-TDT 0.6B (622MB) STT engine."""
    try:
        tdt = ParakeetTDT()
        print("[OK] Active STT: NVIDIA Parakeet-TDT 0.6B (622MB, sub-300ms latency)")
        return tdt
    except Exception as e:
        print(f"[Warning] Parakeet-TDT error ({e}).")
        return None
