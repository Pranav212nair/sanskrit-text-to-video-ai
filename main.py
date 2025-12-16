import chainlit as cl
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from utility.script.script_generator import generate_script
from utility.audio.audio_generator import generate_audio
# from utility.captions.timed_captions_generator import generate_timed_captions
from utility.video.background_video_generator import generate_video_url
from utility.video.video_search_query_generator import getVideoSearchQueriesTimed, merge_empty_intervals
from utility.render.render_engine import get_output_media

# Create a thread pool for long-running operations
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="chainlit-")

def announce(msg):
    return cl.Message(content=msg, author="system")

@cl.on_message
async def main_chat(message: cl.Message):
    # 1. Input: Sanskrit from user
    sanskrit_text = message.content.strip()
    print(f"[APP] Received input: {sanskrit_text}")
    await cl.Message(content="Translating Sanskrit and creating story with a moral...", author="system").send()

    try:
        # 2. Generate story with moral (calls Groq sync, so use thread executor)
        loop = asyncio.get_running_loop()
        print("[APP] Generating script...")
        script = await loop.run_in_executor(executor, generate_script, sanskrit_text)
        print(f"[APP] Script generated: {len(script)} chars")
        await cl.Message(content=f"Story generated!\n\n**{script}**", author="system").send()
    except Exception as e:
        print(f"[ERROR] Story generation failed: {e}")
        import traceback
        traceback.print_exc()
        await cl.Message(content=f"❌ Error during story generation: {str(e)}", author="system").send()
        return

    # 3. Generate Audio
    audio_file = "audio_tts.wav"
    await cl.Message(content="Generating narration audio for the story...", author="system").send()
    try:
        print("[APP] Generating audio...")
        await generate_audio(script, audio_file)
        # Convert to absolute path for render engine
        audio_file = os.path.abspath(audio_file)
        print(f"[APP] Audio generated: {audio_file}")
        await cl.Message(content="Audio generated!", author="system").send()
    except Exception as e:
        print(f"[ERROR] Audio generation failed: {e}")
        import traceback
        traceback.print_exc()
        await cl.Message(content=f"❌ Error during audio generation: {str(e)}", author="system").send()
        return

    # 4. Generate simple timed captions (without Whisper dependency)
    await cl.Message(content="Generating captions...", author="system").send()
    timed_captions = []
    try:
        print("[APP] Generating captions...")
        # Simple caption: split script into sentences with basic timing
        sentences = script.split('. ')
        approx_duration = 3  # ~3 seconds per sentence (adjust based on audio)
        current_time = 0
        for sentence in sentences:
            if sentence.strip():
                # Format: [[start, end], text]
                timed_captions.append([[current_time, current_time + approx_duration], sentence.strip() + '.'])
                current_time += approx_duration
        print(f"[APP] Generated {len(timed_captions)} captions")
        await cl.Message(content=f"Captions generated!", author="system").send()
    except Exception as e:
        print(f"[WARNING] Caption generation failed: {e}")
        await cl.Message(content=f"⚠️ Warning during caption generation: {str(e)}", author="system").send()
        timed_captions = []

    # 5. Generate video search queries
    await cl.Message(content="Generating video search queries...", author="system").send()
    queries = []
    try:
        print("[APP] Generating video search queries...")
        loop = asyncio.get_running_loop()
        queries = await loop.run_in_executor(executor, getVideoSearchQueriesTimed, script, timed_captions)
        queries = merge_empty_intervals(queries)
        print(f"[APP] Generated {len(queries)} query intervals")
        await cl.Message(content=f"Search queries created!", author="system").send()
    except Exception as e:
        print(f"[WARNING] Query generation failed: {e}")
        import traceback
        traceback.print_exc()
        await cl.Message(content=f"⚠️ Warning during query generation: {str(e)}", author="system").send()

    # 6. Search for background videos
    await cl.Message(content="Searching for background videos on Pexels...", author="system").send()
    videos = []
    try:
        print("[APP] Searching for background videos...")
        loop = asyncio.get_running_loop()
        videos = await loop.run_in_executor(executor, generate_video_url, queries, "pexel")
        print(f"[APP] Found {len(videos)} video intervals")
        await cl.Message(content=f"Found {len(videos)} video clips!", author="system").send()
    except Exception as e:
        print(f"[WARNING] Video search failed: {e}")
        import traceback
        traceback.print_exc()
        await cl.Message(content=f"⚠️ Warning during video search: {str(e)}", author="system").send()

    # 7. Render final video
    await cl.Message(content="Rendering final video with audio and captions...", author="system").send()
    try:
        print("[APP] Starting video rendering...")
        loop = asyncio.get_running_loop()
        
        # Run rendering with timeout to prevent blocking
        try:
            output_file = await asyncio.wait_for(
                loop.run_in_executor(executor, get_output_media, audio_file, timed_captions, videos, "pexel"),
                timeout=300.0  # 5 minute timeout
            )
        except asyncio.TimeoutError:
            print("[ERROR] Video rendering timed out after 5 minutes")
            await cl.Message(content="⏱️ Video rendering is taking too long. Please try with a shorter story.", author="system").send()
            return
        
        print(f"[APP] Video rendering complete: {output_file}")
        
        # Send video to chat with playable player
        if os.path.exists(output_file):
            elements = [cl.File(name="output_video.mp4", path=output_file, display="inline")]
            await cl.Message(content="✅ Video successfully generated!", author="system", elements=elements).send()
        else:
            await cl.Message(content=f"❌ Video file not found: {output_file}", author="system").send()
    except Exception as e:
        print(f"[ERROR] Video rendering failed: {e}")
        import traceback
        traceback.print_exc()
        await cl.Message(content=f"❌ Error during video rendering: {str(e)}", author="system").send()
        return
