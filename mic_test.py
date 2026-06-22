import pyaudio
import numpy as np
import time

p = pyaudio.PyAudio()
print("Scanning all microphones for 1 second each to find audio...\n")

for i in range(p.get_device_count()):
    dev = p.get_device_info_by_index(i)
    if dev['maxInputChannels'] > 0:
        print(f"Testing Device {i}: {dev['name']}")
        try:
            stream = p.open(format=pyaudio.paInt16,
                            channels=1,
                            rate=16000,
                            input=True,
                            input_device_index=i,
                            frames_per_buffer=1024)
            # Read 1 second of audio
            data = stream.read(1024 * 16, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            vol = int(np.abs(audio_data).mean())
            print(f"   -> Volume detected: {vol}")
            stream.close()
        except Exception as e:
            print(f"   -> Error: {e}")

p.terminate()
