import os 
import requests
from utility.utils import log_response,LOG_TYPE_PEXEL
from dotenv import load_dotenv

load_dotenv()
PEXELS_API_KEY = os.environ.get('PEXELS_KEY')

def get_images_for_video(timed_video_searches):
    # Placeholder for future Stable Diffusion support
    return [[interval, None] for interval, _ in timed_video_searches]

def search_videos(query_string, orientation_landscape=True):
   
    if not PEXELS_API_KEY:
        print("[PEXELS] Missing PEXELS_KEY env var. Skipping search for:", query_string)
        return {"videos": []}

    url = "https://api.pexels.com/videos/search"
    headers = {
        "Authorization": PEXELS_API_KEY,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    params = {
        "query": query_string,
        "per_page": 40  # Increased from 15 to 40 for more results
    }

    try:
        print(f"[PEXELS] Searching: '{query_string}' (requesting up to 40 results)")
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        json_data = response.json()
        log_response(LOG_TYPE_PEXEL,query_string,json_data)
        print(f"[PEXELS] Received {len(json_data.get('videos', []))} videos for '{query_string}'")
        return json_data
    except Exception as e:
        print(f"[PEXELS] Error for '{query_string}':", e)
        return {"videos": []}


def getBestVideo(query_string, orientation_landscape=True, used_vids=None):
    if used_vids is None:
        used_vids = []
    vids = search_videos(query_string, orientation_landscape)
    videos = vids.get('videos', [])  # Extract the videos list from JSON
    print(f"[PEXELS] Filtering best video for '{query_string}', candidates: {len(videos)}")

    # Filter videos - be lenient with resolution requirements
    filtered_videos = [video for video in videos if video['width'] >= 1280 and video['height'] >= 720]
    
    print(f"[PEXELS] Candidates after 1280x720+ filter: {len(filtered_videos)}")
    
    if not filtered_videos:
        # If strict filtering fails, take any video (lower quality fallback)
        print(f"[PEXELS] Relaxing to any resolution for '{query_string}'")
        filtered_videos = [video for video in videos if video.get('video_files')]

    # Sort the filtered videos by duration in ascending order (prefer ~15 second clips)
    sorted_videos = sorted(filtered_videos, key=lambda x: abs(15-int(x.get('duration', 15))))

    # Extract the first suitable video URL
    for video in sorted_videos:
        video_files = video.get('video_files', [])
        
        # Sort video files by quality/resolution - PREFER HD (1920x1080) or SD over UHD to reduce download time
        # This significantly speeds up processing
        def quality_score(vf):
            w, h = vf.get('width', 0), vf.get('height', 0)
            quality = vf.get('quality', '')
            
            # Prefer 1920x1080 (HD), then 1280x720 (SD), avoid 4K+ to save time
            if w == 1920 and h == 1080:
                return 100  # Best choice - fast and good quality
            elif w == 1280 and h == 720:
                return 90   # Good fallback
            elif w < 1920 and h < 1080 and w >= 1280 and h >= 720:
                return 80   # Acceptable
            else:
                return -abs(w * h - (1920 * 1080))  # Penalize UHD/4K heavily
        
        video_files_sorted = sorted(video_files, key=quality_score, reverse=True)
        
        for video_file in video_files_sorted:
            # Accept landscape videos >= 1280x720 or any landscape orientation
            file_link = video_file.get('link', '')
            if file_link and (file_link.split('.hd')[0] not in used_vids):
                vf_width = video_file.get('width', 0)
                vf_height = video_file.get('height', 0)
                
                if vf_width >= 1280 and vf_height >= 720:
                    print(f"[PEXELS] ✅ Selected: {vf_width}x{vf_height} - {video_file.get('quality', 'unknown')}")
                    return file_link
    
    print(f"[PEXELS] ❌ No suitable video found for: '{query_string}'")
    return None


def generate_video_url(timed_video_searches, video_server):
    timed_video_urls = []
    if video_server == "pexel":
        used_links = []
        print(f"[PEXELS] Starting video search for {len(timed_video_searches)} intervals")
        for (t1, t2), search_terms in timed_video_searches:
            url = None
            print(f"[PEXELS] Processing interval [{t1}, {t2}] with queries: {search_terms}")
            
            # Try all provided search terms
            for query in search_terms:
                print(f"[PEXELS] Trying query '{query}' for interval [{t1}, {t2}]...")
                url = getBestVideo(query, orientation_landscape=True, used_vids=used_links)
                if url:
                    used_links.append(url.split('.hd')[0])
                    print(f"[PEXELS] ✅ Found video for query '{query}'")
                    break
            
            # If no video found, try fallback generic queries
            if not url:
                fallback_queries = ["nature", "landscape", "beautiful", "outdoor", "background", "abstract", "color", "motion"]
                print(f"[PEXELS] No video found with provided queries, trying fallbacks...")
                for fallback in fallback_queries:
                    print(f"[PEXELS] Trying fallback query '{fallback}' for interval [{t1}, {t2}]...")
                    url = getBestVideo(fallback, orientation_landscape=True, used_vids=used_links)
                    if url:
                        used_links.append(url.split('.hd')[0])
                        print(f"[PEXELS] ✅ Found fallback video: {url}")
                        break
            
            if url:
                print(f"[PEXELS] ✅ FINAL: Found video for interval [{t1}, {t2}]: {url}")
            else:
                print(f"[PEXELS] ❌ FINAL: No video found for interval [{t1}, {t2}]")
            
            timed_video_urls.append([[t1, t2], url])
        
        print(f"[PEXELS] Video search complete: {len([v for v in timed_video_urls if v[1] is not None])}/{len(timed_video_urls)} intervals have videos")
    elif video_server == "stable_diffusion":
        timed_video_urls = get_images_for_video(timed_video_searches)

    return timed_video_urls
