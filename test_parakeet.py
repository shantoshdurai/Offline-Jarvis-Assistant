import wave
import time
import numpy as np
import scipy.signal
from parakeet_stt import ParakeetEOU

print("Loading NVIDIA Parakeet-EOU-120M INT8 model...")
t0 = time.time()
p = ParakeetEOU()
print(f"Loaded model in {time.time() - t0:.2f}s from {p.model_dir}")

try:
    with wave.open("input.wav", "rb") as wf:
        sr = wf.getframerate()
        n_channels = wf.getnchannels()
        raw = wf.readframes(wf.getnframes())
        data = np.frombuffer(raw, dtype=np.int16)
        if n_channels > 1:
            data = data[::n_channels]
        duration = len(data) / sr
        print(f"\nTesting transcription on input.wav ({duration:.2f}s of audio)...")
        if sr != 16000:
            num_samples = int(len(data) * 16000 / sr)
            data = scipy.signal.resample(data.astype(np.float32), num_samples).astype(np.int16)

        t_infer_start = time.time()
        text = p.transcribe(data)
        infer_time = time.time() - t_infer_start

        print(f"Transcribed Text: \"{text}\"")
        print(f"Inference Latency: {infer_time*1000:.1f} ms ({duration/infer_time:.1f}x Real-Time Speed)")
except Exception as e:
    print(f"Error testing input.wav: {e}")
