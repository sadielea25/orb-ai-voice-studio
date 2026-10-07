import sounddevice as sd
import numpy as np
def check_mic():
    try:
        print('Testing default input...')
        rec = sd.rec(int(2 * 44100), samplerate=44100, channels=1, blocking=True)
        volume = np.linalg.norm(rec) * 10
        print('Volume level:', volume)
    except Exception as e:
        print('ERROR:', e)
check_mic()
