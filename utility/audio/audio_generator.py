# utility/audio/audio_generator.py
import os
<<<<<<< HEAD
import edge_tts


async def generate_audio(text: str, outputFilename: str,
                         voice: str = "en-US-AriaNeural",
                         speed: float = 1.0) -> str:
    """Generate narration with Edge TTS, falling back to the local engine."""
    if not text.strip():
        raise ValueError("Cannot generate audio from empty text")

    try:
        rate = f"{int((speed - 1.0) * 100):+d}%"
        communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
        await communicate.save(outputFilename)
        actual_output = outputFilename
    except Exception as exc:
        print(f"[AUDIO] Edge TTS unavailable ({exc.__class__.__name__}); using local fallback")
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", int(150 * speed))
            root, ext = os.path.splitext(outputFilename)
            actual_output = root + ".wav"
            engine.save_to_file(text, actual_output)
            engine.runAndWait()
            engine.stop()
        except Exception as fallback_exc:
            raise RuntimeError("No text-to-speech engine is available") from fallback_exc

    if not os.path.exists(actual_output) or os.path.getsize(actual_output) == 0:
        raise RuntimeError("Audio file was not created")

    size_kb = os.path.getsize(actual_output) / 1024
    print(f"[AUDIO] Audio file created successfully: {actual_output} ({size_kb:.1f} KB)")
    return actual_output
=======
from pathlib import Path
import pyttsx3
import time
from dotenv import load_dotenv

load_dotenv()

# voice: use system voices, speed is in words per minute (default 150)
async def generate_audio(text: str, outputFilename: str,
                         voice: int = 0,
                         speed: float = 1.0) -> None:
    """
    Generate speech audio from text using pyttsx3 (completely free, offline)
    
    Args:
        text: Text to convert to speech
        outputFilename: Output audio file path (will be saved as .wav)
        voice: Voice index (0=default, 1=alternative if available)
        speed: Playback speed multiplier (1.0=normal)
    """
    # Create a new engine instance for each call to ensure clean state
    engine = pyttsx3.init()
    engine.setProperty('rate', int(150 * speed))
    
    # Get available voices
    voices = engine.getProperty('voices')
    if voice < len(voices):
        engine.setProperty('voice', voices[voice].id)
    
    # Generate speech
    print(f"[AUDIO] Generating speech to file: {outputFilename}")
    engine.save_to_file(text, outputFilename)
    engine.runAndWait()
    
    # Wait a moment to ensure file is written
    time.sleep(0.5)
    
    # Verify file was created
    if os.path.exists(outputFilename):
        size_kb = os.path.getsize(outputFilename) / 1024
        print(f"[AUDIO] Audio file created successfully: {outputFilename} ({size_kb:.1f} KB)")
    else:
        print(f"[AUDIO] Warning: Audio file not found at {outputFilename}")
    
    engine.stop()
>>>>>>> f06b6eb077bf034673c1e548e6a2a71ab1aa60e6
