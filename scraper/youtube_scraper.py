import os
import sys
import json
import re
import time
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api import TranscriptsDisabled
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.tagging import generate_tags, detect_language
from utils.chunking import chunk_content
from scoring.trust_score import calculate_trust_score

from dotenv import load_dotenv
import os
load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_API_SERVICE = "youtube"
YOUTUBE_API_VERSION = "v3"

REQUEST_DELAY = 0.5  

def extract_video_id(url: str) -> str | None:
    if not url:
        return None

    # Standard youtube.com/watch?v=ID format
    parsed = urlparse(url)
    if "youtube.com" in parsed.netloc:
        query_params = parse_qs(parsed.query)
        video_ids = query_params.get("v", [])
        if video_ids:
            return video_ids[0]

        # Embedded format: youtube.com/embed/ID
        if "/embed/" in parsed.path:
            return parsed.path.split("/embed/")[1].split("?")[0]

    # Short format: youtu.be/ID
    if "youtu.be" in parsed.netloc:
        # Path is "/VIDEO_ID" — strip the leading slash
        video_id = parsed.path.lstrip("/")
        # Remove any trailing parameters
        video_id = video_id.split("?")[0].split("&")[0]
        if video_id:
            return video_id

    # Regex fallback — catches any remaining formats
    # Matches 11-character video IDs (YouTube's standard ID length)
    pattern = r"(?:v=|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})"
    match = re.search(pattern, url)
    if match:
        return match.group(1)

    print(f"[YouTube] Could not extract video ID from: {url}")
    return None

def fetch_video_metadata(video_id: str) -> dict:
    if not YOUTUBE_API_KEY or YOUTUBE_API_KEY == "YOUR_YOUTUBE_API_KEY_HERE":
        print("[YouTube] WARNING: No API key set. Metadata fetch will fail.")
        print("[YouTube] Get a free key at: console.cloud.google.com")
        return {}

    try:
        service = build(
            YOUTUBE_API_SERVICE,
            YOUTUBE_API_VERSION,
            developerKey=YOUTUBE_API_KEY
        )

        time.sleep(REQUEST_DELAY)

        request = service.videos().list(
            part="snippet,statistics",
            id=video_id
        )
        response = request.execute()

        items = response.get("items", [])
        if not items:
            print(f"[YouTube] No video found for ID: {video_id}")
            return {}

        video = items[0]
        snippet    = video.get("snippet", {})
        statistics = video.get("statistics", {})

        return {
            "video_id":     video_id,
            "title":        snippet.get("title", "Unknown Title"),
            "channel":      snippet.get("channelTitle", "Unknown Channel"),
            "published_at": snippet.get("publishedAt", "")[:10],  
            "description":  snippet.get("description", ""),
            "tags":         snippet.get("tags", []),  
            "view_count":   int(statistics.get("viewCount", 0)),
            "like_count":   int(statistics.get("likeCount", 0)),
            "url":          f"https://www.youtube.com/watch?v={video_id}",
        }

    except HttpError as e:
        print(f"[YouTube] API error for video {video_id}: {e}")
        return {}
    except Exception as e:
        print(f"[YouTube] Unexpected error for video {video_id}: {e}")
        return {}

def fetch_transcript(video_id: str) -> str:
    """Fetches transcript using youtube-transcript-api v1.x"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        ytt = YouTubeTranscriptApi()
        transcript_data = ytt.fetch(video_id)
        full_transcript = " ".join(
            snippet.text.strip()
            for snippet in transcript_data
            if snippet.text.strip()
        )
        full_transcript = re.sub(r'\[.*?\]', '', full_transcript)
        full_transcript = re.sub(r'\s+', ' ', full_transcript).strip()
        
        print(f"[YouTube] Transcript length: {len(full_transcript)} characters")
        return full_transcript

    except TranscriptsDisabled:
        print(f"[YouTube] Transcripts disabled for: {video_id}")
        return ""
    except Exception as e:
        print(f"[YouTube] Transcript fetch failed for {video_id}: {e}")
        return ""

def scrape_youtube_video(url: str) -> dict:
    print(f"\n[YouTube] Scraping: {url}")
    video_id = extract_video_id(url)
    if not video_id:
        print(f"[YouTube] Invalid URL: {url}")
        return {}

    print(f"[YouTube] Video ID: {video_id}")
    metadata = fetch_video_metadata(video_id)
    transcript = fetch_transcript(video_id)

    if not metadata and not transcript:
        print(f"[YouTube] Could not fetch any data for: {url}")
        return {}

    title       = metadata.get("title", "Unknown Title")
    channel     = metadata.get("channel", "Unknown Channel")
    published   = metadata.get("published_at", "Unknown")
    description = metadata.get("description", "")
    yt_tags     = metadata.get("tags", [])

    content = transcript if transcript else description
    full_text_for_tags = f"{title} {description} {transcript[:2000]}"

    language = detect_language(content[:500] if content else title)
    auto_tags = generate_tags(full_text_for_tags)
    combined_tags = list(dict.fromkeys(auto_tags + yt_tags[:3]))[:10]
    chunks = chunk_content(content, source_type="youtube") if content else []

    trust_result = calculate_trust_score(
        url=url,
        author=channel,
        published_date=published,
        content=content[:3000] if content else "",
        citation_count=None,
        source_type="youtube"
    )
    result = {
        "source_url":      url,
        "source_type":     "youtube",
        "author":          channel,
        "published_date":  published,
        "language":        language,
        "region":          "Global",  # YouTube doesn't expose region per-video
        "topic_tags":      combined_tags,
        "trust_score":     trust_result["trust_score"],
        "content_chunks":  chunks,
        # Extra context fields
        "_title":              title,
        "_video_id":           video_id,
        "_has_transcript":     bool(transcript),
        "_transcript_length":  len(transcript),
        "_description_length": len(description),
        "_view_count":         metadata.get("view_count", 0),
        "_trust_breakdown":    trust_result["factor_breakdown"],
    }

    print(f"[YouTube] Title: {title[:60]}...")
    print(f"[YouTube] Channel: {channel}")
    print(f"[YouTube] Published: {published}")
    print(f"[YouTube] Transcript: {'Yes' if transcript else 'No'}")
    print(f"[YouTube] Trust score: {trust_result['trust_score']}")
    print(f"[YouTube] Tags: {combined_tags[:5]}")

    return result


def scrape_multiple_videos(urls: list) -> list:
    """Scrapes multiple YouTube URLs and returns list of results."""
    results = []
    for url in urls:
        result = scrape_youtube_video(url)
        if result:
            results.append(result)
        else:
            print(f"[YouTube] Skipping failed URL: {url}")
    return results


def save_to_json(data: list, filepath: str = "output/youtube.json"):
    """Saves list of scraped videos to JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n[YouTube] Saved {len(data)} videos to {filepath}")


if __name__ == "__main__":
    VIDEO_URLS = [
        "https://www.youtube.com/watch?v=zjkBMFhNj_g",  
        "https://www.youtube.com/watch?v=aircAruvnKk",  
    ]

    results = scrape_multiple_videos(VIDEO_URLS)

    if results:
        save_to_json(results, "output/youtube.json")
        print(f"\n=== SUMMARY ===")
        for r in results:
            print(f"URL: {r['source_url'][:50]}...")
            print(f"  Channel: {r['author']}")
            print(f"  Date: {r['published_date']}")
            print(f"  Trust: {r['trust_score']}")
            print(f"  Transcript: {r.get('_has_transcript', False)}")
            print(f"  Tags: {r['topic_tags'][:3]}")
            print()