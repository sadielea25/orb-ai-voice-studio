"""
test_mic.py
Quick test for sounddevice audio capture and speech recognition.
"""
import io
import wave
import numpy as np
import sounddevice as sd
import speech_recognition as sr

def test_mic_level():
    duration = 2.0  # seconds
    sample_rate = 16000
    print("Testing mic level for 2 seconds... Speak now!")
    audio_data = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
    sd.wait()
    rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
    print(f"Captured audio! RMS energy level: {rms:.2f}")

if __name__ == "__main__":
    test_mic_level()
