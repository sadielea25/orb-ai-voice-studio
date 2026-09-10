import os
import sys
import asyncio
import ctypes
import edge_tts

winmm = ctypes.windll.winmm
VOICE = "en-GB-SoniaNeural"  # Natural UK English Voice

async def generate_speech(text, output_file):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_file)

def play_audio(filepath):
    abs_path = os.path.abspath(filepath)
    alias = "voice_track"
    winmm.mciSendStringW(f"close {alias}", None, 0, None)
    ret = winmm.mciSendStringW(f'open "{abs_path}" type mpegvideo alias {alias}', None, 0, None)
    if ret == 0:
        winmm.mciSendStringW(f"play {alias} wait", None, 0, None)
        winmm.mciSendStringW(f"close {alias}", None, 0, None)
    else:
        # Fallback to powershell sound player / media player
        pass

def speak(text):
    temp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "speech_temp.mp3")
    try:
        asyncio.run(generate_speech(text, temp_file))
        play_audio(temp_file)
    except Exception as e:
        print(f"Error speaking: {e}")

if __name__ == "__main__":
    text_to_say = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hello! Your natural voice assistant is ready."
    print(f"Speaking: {text_to_say}")
    speak(text_to_say)
