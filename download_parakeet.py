"""Script to download NVIDIA Parakeet-EOU-120M INT8 ONNX models from HuggingFace."""

import os
import sys
import urllib.request

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO_URL = "https://huggingface.co/soniqo/Parakeet-EOU-120M-ONNX-INT8/resolve/main"

FILES = [
    "parakeet-eou-encoder.onnx",
    "parakeet-eou-decoder.onnx",
    "parakeet-eou-joint.onnx",
    "vocab.json",
    "config.json"
]


def download_progress(block_num, block_size, total_size):
    downloaded = block_num * block_size
    if total_size > 0:
        percent = min(100.0, downloaded * 100.0 / total_size)
        mb_down = downloaded / (1024 * 1024)
        mb_tot = total_size / (1024 * 1024)
        sys.stdout.write(f"\r   [{percent:5.1f}%] {mb_down:6.1f} MB / {mb_tot:6.1f} MB")
        sys.stdout.flush()


def main():
    target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "parakeet-eou-120m")
    os.makedirs(target_dir, exist_ok=True)

    print("============================================================")
    print(" Downloading NVIDIA Parakeet-EOU-120M INT8 ONNX Models")
    print(f" Target Directory: {target_dir}")
    print("============================================================\n")

    for fname in FILES:
        dest_path = os.path.join(target_dir, fname)
        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
            print(f"[OK] {fname} already exists ({os.path.getsize(dest_path) / (1024*1024):.1f} MB)")
            continue

        file_url = f"{REPO_URL}/{fname}"
        print(f"[*] Downloading {fname}...")
        try:
            urllib.request.urlretrieve(file_url, dest_path, reporthook=download_progress)
            print(f"\n[OK] Saved {fname}")
        except Exception as e:
            print(f"\n[!] Error downloading {fname}: {e}")
            if os.path.exists(dest_path):
                os.remove(dest_path)

    print("\n[OK] Model setup complete! You can now run fast_agent.py.")


if __name__ == "__main__":
    main()
