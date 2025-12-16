import time
import os
import tempfile
import zipfile
import platform
import subprocess
from moviepy.editor import (AudioFileClip, CompositeVideoClip, CompositeAudioClip, ImageClip,
                            TextClip, VideoFileClip, ColorClip)
from moviepy.audio.fx.audio_loop import audio_loop
from moviepy.audio.fx.audio_normalize import audio_normalize
import requests

def download_file(url, filename):
    print(f"[RENDER] Downloading video: {url}")
    with open(filename, 'wb') as f:
        headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        f.write(response.content)
    try:
        size_mb = os.path.getsize(filename) / (1024 * 1024)
        print(f"[RENDER] Downloaded to {filename} ({size_mb:.2f} MB)")
    except Exception:
        pass

def search_program(program_name):
    try: 
        search_cmd = "where" if platform.system() == "Windows" else "which"
        return subprocess.check_output([search_cmd, program_name], stderr=subprocess.DEVNULL).decode().strip()
    except subprocess.CalledProcessError:
        return None

def get_program_path(program_name):
    program_path = search_program(program_name)
    return program_path

def get_output_media(audio_file_path, timed_captions, background_video_data, video_server):
    OUTPUT_FILE_NAME = "rendered_video.mp4"
    magick_path = get_program_path("magick")
    imagemagick_available = False
    if magick_path:
        os.environ['IMAGEMAGICK_BINARY'] = magick_path
        imagemagick_available = True
    
    print("[RENDER] Starting composition pipeline...")
    visual_clips = []
    temp_video_paths = []
    TARGET_WIDTH, TARGET_HEIGHT = 1920, 1080
    
    # Get total duration from audio for fallback backgrounds
    total_duration = 1.0
    if os.path.exists(audio_file_path) and os.path.getsize(audio_file_path) > 0:
        try:
            audio_probe = AudioFileClip(audio_file_path)
            total_duration = float(audio_probe.duration)
            audio_probe.close()
            print(f"[RENDER] Audio duration: {total_duration}s")
        except Exception as e:
            print(f"[RENDER] Could not detect audio duration: {e}")
    
    for (t1, t2), video_url in background_video_data:
        interval_duration = max(0.1, float(t2) - float(t1))
        
        # If video URL exists, try to use it
        if video_url:
            try:
                # Download the video file
                # Use .mp4 suffix so ffmpeg/moviepy can infer the correct reader on Windows
                video_filename = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
                download_file(video_url, video_filename)
                temp_video_paths.append(video_filename)
                
                # Create VideoFileClip from the downloaded file
                print(f"[RENDER] Creating clip from {video_filename}")
                video_clip = VideoFileClip(video_filename)
                
                # Trim the clip to the target interval length and position at t1
                video_clip = video_clip.subclip(0, min(interval_duration, video_clip.duration))
                
                # Resize video to fit 1920x1080 canvas while maintaining aspect ratio
                original_width, original_height = video_clip.size
                print(f"[RENDER] Video original size: {original_width}x{original_height}")
                
                # Calculate scaling to fit canvas while maintaining aspect ratio
                scale_factor = max(TARGET_WIDTH / original_width, TARGET_HEIGHT / original_height)
                new_width = int(original_width * scale_factor)
                new_height = int(original_height * scale_factor)
                
                print(f"[RENDER] Scaling to: {new_width}x{new_height}")
                video_clip = video_clip.resize(width=new_width, height=new_height)
                
                # Center the video on the 1920x1080 canvas
                video_clip = video_clip.set_position(("center", "center"))
                
                video_clip = video_clip.set_start(t1)
                visual_clips.append(video_clip)
                print(f"[RENDER] ✅ Added video clip for interval [{t1}, {t2}]")
                continue
            except Exception as e:
                print(f"[RENDER] Video processing failed: {e}, creating fallback background")
        
        # Fallback: Create solid color background for this interval
        try:
            from PIL import Image
            import tempfile as tmp_module
            
            # Create a solid colored background (cycle through colors)
            color_index = int(t1) % 5
            colors = [(20, 30, 80), (40, 60, 120), (60, 40, 100), (80, 30, 60), (30, 50, 90)]
            bg_color = colors[color_index]
            
            fallback_img_path = tmp_module.NamedTemporaryFile(suffix=".png", delete=False).name
            img = Image.new('RGB', (1920, 1080), color=bg_color)
            img.save(fallback_img_path)
            
            fallback_clip = ImageClip(fallback_img_path).set_duration(interval_duration)
            fallback_clip = fallback_clip.set_start(t1)
            visual_clips.append(fallback_clip)
            print(f"[RENDER] ⚠️ Created fallback background for interval [{t1}, {t2}]")
        except Exception as e:
            print(f"[RENDER] Could not create fallback: {e}")
            # Last resort: create a solid color clip
            try:
                solid_clip = ColorClip(size=(1920, 1080), color=(40, 60, 120)).set_duration(interval_duration).set_start(t1)
                visual_clips.append(solid_clip)
                print(f"[RENDER] Created ColorClip fallback for [{t1}, {t2}]")
            except Exception as e2:
                print(f"[RENDER] Failed to create any background: {e2}")
    
    audio_clips = []
    if os.path.exists(audio_file_path) and os.path.getsize(audio_file_path) > 0:
        try:
            audio_file_clip = AudioFileClip(audio_file_path)
            audio_clips.append(audio_file_clip)
            print(f"[RENDER] Audio file loaded: {audio_file_path} (Duration: {audio_file_clip.duration}s)")
        except Exception as e:
            print(f"[RENDER] Warning: Could not load audio file: {e}")
    else:
        print(f"[RENDER] Warning: Audio file not found or empty: {audio_file_path}")

    if imagemagick_available:
        for (t1, t2), text in timed_captions:
            try:
                text_clip = TextClip(txt=text, fontsize=100, color="white", stroke_width=3, stroke_color="black", method="label")
                text_clip = text_clip.set_start(t1)
                text_clip = text_clip.set_end(t2)
                text_clip = text_clip.set_position(["center", 800])
                visual_clips.append(text_clip)
            except Exception:
                # If TextClip fails, skip subtitle for this segment
                continue
    else:
        # Fallback: Create text clips without ImageMagick using PIL
        print("[RENDER] ImageMagick not available. Creating captions with PIL fallback...")
        for (t1, t2), text in timed_captions:
            try:
                from PIL import Image, ImageDraw, ImageFont
                import tempfile as tmp_module
                
                # Create a temporary image with text
                img = Image.new('RGBA', (1920, 200), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                
                # Try to use a reasonable font, fallback to default
                try:
                    font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 60)
                except:
                    font = ImageFont.load_default()
                
                # Draw text with white color
                draw.text((100, 50), text, fill=(255, 255, 255, 255), font=font)
                
                # Save temporarily
                tmp_img_path = tmp_module.NamedTemporaryFile(suffix=".png", delete=False).name
                img.save(tmp_img_path)
                
                # Create clip from image
                text_clip = ImageClip(tmp_img_path).set_duration(float(t2) - float(t1))
                text_clip = text_clip.set_start(t1)
                text_clip = text_clip.set_position(["center", 850])
                visual_clips.append(text_clip)
            except Exception as e:
                print(f"[RENDER] Warning: Could not create caption for '{text}': {e}")
                continue

    # If no visual clips could be created, fall back to a gradient background with text
    if not visual_clips:
        fallback_duration = 1.0
        try:
            audio_probe = AudioFileClip(audio_file_path)
            fallback_duration = max(fallback_duration, float(audio_probe.duration))
            audio_probe.close()
        except Exception:
            pass
        
        print("[RENDER] No video clips found. Creating fallback background with captions...")
        
        # Create a nice gradient background (dark blue to purple)
        from PIL import Image, ImageDraw
        import tempfile as tmp_module
        
        try:
            fallback_img_path = tmp_module.NamedTemporaryFile(suffix=".png", delete=False).name
            img = Image.new('RGB', (1920, 1080), color=(20, 30, 80))
            draw = ImageDraw.Draw(img)
            
            # Add a simple gradient manually
            for y in range(1080):
                # Gradient from dark blue to purple
                r = int(20 + (y / 1080) * 80)
                g = int(30 + (y / 1080) * 20)
                b = int(80 + (y / 1080) * 100)
                draw.line([(0, y), (1920, y)], fill=(r, g, b))
            
            img.save(fallback_img_path)
            fallback_clip = ImageClip(fallback_img_path).set_duration(fallback_duration)
            visual_clips.append(fallback_clip)
        except Exception as e:
            print(f"[RENDER] Could not create gradient background: {e}. Using solid color...")
            visual_clips = [ColorClip(size=(1920, 1080), color=(40, 60, 120)).set_duration(fallback_duration)]
        
        # Add captions to the fallback background
        for (t1, t2), text in timed_captions:
            try:
                from PIL import Image, ImageDraw, ImageFont
                
                # Create a temporary image with text
                txt_img = Image.new('RGBA', (1920, 300), (0, 0, 0, 0))
                txt_draw = ImageDraw.Draw(txt_img)
                
                # Try to use a reasonable font
                try:
                    font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 70)
                except:
                    font = ImageFont.load_default()
                
                # Draw text with white color
                txt_draw.text((100, 50), text, fill=(255, 255, 255, 255), font=font)
                
                # Save temporarily
                tmp_txt_path = tmp_module.NamedTemporaryFile(suffix=".png", delete=False).name
                txt_img.save(tmp_txt_path)
                
                # Create clip from image
                txt_clip = ImageClip(tmp_txt_path).set_duration(float(t2) - float(t1))
                txt_clip = txt_clip.set_start(t1)
                txt_clip = txt_clip.set_position(["center", 850])
                visual_clips.append(txt_clip)
            except Exception as e:
                print(f"[RENDER] Warning: Could not add caption to fallback: {e}")
                continue

    print(f"[RENDER] Total visual clips: {len(visual_clips)} (videos + captions)")
    print(f"[RENDER] Creating composite video with size (1920, 1080)")
    video = CompositeVideoClip(visual_clips, size=(1920, 1080))
    
    if audio_clips:
        audio = CompositeAudioClip(audio_clips)
        video.duration = audio.duration
        video.audio = audio
        print(f"[RENDER] Audio attached. Video duration: {video.duration}s")
    else:
        print(f"[RENDER] Warning: No audio attached to video")

    print("[RENDER] Starting ffmpeg encoding...")
    video.write_videofile(
        OUTPUT_FILE_NAME,
        codec='libx264',
        audio_codec='aac',
        fps=25,
        preset='veryfast',
        threads=4,
        logger='bar'
    )
    print(f"[RENDER] Encoding complete: {OUTPUT_FILE_NAME}")

    try:
        video.close()
    except Exception:
        pass
    
    # Clean up downloaded files
    for video_filename in temp_video_paths:
        try:
            os.remove(video_filename)
        except Exception:
            pass

    return OUTPUT_FILE_NAME