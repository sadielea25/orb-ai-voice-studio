import os
import ctypes
import time

winmm = ctypes.windll.winmm
alias = f"test_{int(time.time()*1000)%10000}"
path = os.path.abspath("speech_seamless.mp3")

print("Target path:", path)
r1 = winmm.mciSendStringW(f"close {alias}", None, 0, None)
r2 = winmm.mciSendStringW(f'open "{path}" type mpegvideo alias {alias}', None, 0, None)
print("Open code:", r2)
t0 = time.time()
r3 = winmm.mciSendStringW(f"play {alias} wait", None, 0, None)
t1 = time.time()
print("Play code:", r3, f"Duration: {t1-t0:.2f}s")
winmm.mciSendStringW(f"close {alias}", None, 0, None)
