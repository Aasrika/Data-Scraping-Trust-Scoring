import json
import os
import time
from datetime import datetime

from scraper.blog_scraper    import scrape_multiple_blogs
from scraper.youtube_scraper import scrape_multiple_videos
from scraper.pubmed_scraper  import scrape_pubmed_article

BLOG_URLS = [
    "https://huggingface.co/blog/llama2",
    "https://blog.google/technology/ai/google-gemini-ai/",
    "https://huggingface.co/blog/rlhf",
]

YOUTUBE_URLS = [
    "https://www.youtube.com/watch?v=zjkBMFhNj_g",  
    "https://www.youtube.com/watch?v=aircAruvnKk",  
]

PUBMED_QUERY = "machine learning natural language processing clinical"

OUTPUT_DIR = "output"

def save_json(data, filepath: str):
    """Saves data to a JSON file, creating directories if needed."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved → {filepath}")

def print_summary(all_results: list):
    """Prints a clean summary table of all scraped sources."""
    print("\n" + "="*70)
    print("SCRAPING SUMMARY")
    print("="*70)
    print(f"{'#':<4} {'Type':<10} {'Trust':<8} {'Author':<25} {'Tags'}")
    print("-"*70)

    for i, result in enumerate(all_results, 1):
        source_type  = result.get("source_type", "unknown")
        trust        = result.get("trust_score", 0)
        author       = result.get("author", "Unknown")[:22]
        tags         = result.get("topic_tags", [])[:2]
        tags_str     = ", ".join(tags)

        print(f"{i:<4} {source_type:<10} {trust:<8} {author:<25} {tags_str}")

    print("-"*70)
    print(f"Total sources scraped: {len(all_results)}")

    if all_results:
        avg_trust = sum(r.get("trust_score", 0) for r in all_results) / len(all_results)
        print(f"Average trust score:   {round(avg_trust, 3)}")
        highest = max(all_results, key=lambda r: r.get("trust_score", 0))
        lowest  = min(all_results, key=lambda r: r.get("trust_score", 0))
        print(f"Highest trust:         {highest.get('trust_score')} ({highest.get('source_type')})")
        print(f"Lowest trust:          {lowest.get('trust_score')} ({lowest.get('source_type')})")
    print("="*70)

def run_pipeline():
    start_time = time.time()
    all_results = []
    failures = []

    print("\n" + "="*70)
    print("DATA SCRAPING PIPELINE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    print(f"\n[PHASE 1] Scraping {len(BLOG_URLS)} blog posts...")
    print("-"*40)

    try:
        blog_results = scrape_multiple_blogs(BLOG_URLS)

        # Track failures
        if len(blog_results) < len(BLOG_URLS):
            failed_count = len(BLOG_URLS) - len(blog_results)
            failures.append(f"Blogs: {failed_count}/{len(BLOG_URLS)} failed")

        all_results.extend(blog_results)
        save_json(blog_results, f"{OUTPUT_DIR}/blogs.json")
        print(f"\n[Phase 1 Complete] {len(blog_results)}/{len(BLOG_URLS)} blogs scraped")

    except Exception as e:
        print(f"[Phase 1 ERROR] Blog scraping failed entirely: {e}")
        failures.append(f"Blogs: complete failure ({e})")

    print(f"\n[PHASE 2] Scraping {len(YOUTUBE_URLS)} YouTube videos...")
    print("-"*40)

    try:
        youtube_results = scrape_multiple_videos(YOUTUBE_URLS)

        if len(youtube_results) < len(YOUTUBE_URLS):
            failed_count = len(YOUTUBE_URLS) - len(youtube_results)
            failures.append(f"YouTube: {failed_count}/{len(YOUTUBE_URLS)} failed")

        all_results.extend(youtube_results)
        save_json(youtube_results, f"{OUTPUT_DIR}/youtube.json")
        print(f"\n[Phase 2 Complete] {len(youtube_results)}/{len(YOUTUBE_URLS)} videos scraped")

    except Exception as e:
        print(f"[Phase 2 ERROR] YouTube scraping failed entirely: {e}")
        failures.append(f"YouTube: complete failure ({e})")

    print(f"\n[PHASE 3] Scraping PubMed article...")
    print("-"*40)

    try:
        pubmed_result = scrape_pubmed_article(PUBMED_QUERY)

        if pubmed_result:
            all_results.append(pubmed_result)
            save_json(pubmed_result, f"{OUTPUT_DIR}/pubmed.json")
            print(f"\n[Phase 3 Complete] PubMed article scraped")
        else:
            failures.append("PubMed: no result returned")
            print(f"\n[Phase 3 FAILED] Could not scrape PubMed article")

    except Exception as e:
        print(f"[Phase 3 ERROR] PubMed scraping failed: {e}")
        failures.append(f"PubMed: complete failure ({e})")

    print(f"\n[SAVING] Combining all results...")

    combined_output = {
        "_metadata": {
            "generated_at":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_sources":  len(all_results),
            "sources_attempted": len(BLOG_URLS) + len(YOUTUBE_URLS) + 1,
            "failures":       failures if failures else "none",
            "pipeline_duration_seconds": round(time.time() - start_time, 2),
        },
        "sources": all_results
    }

    save_json(combined_output, f"{OUTPUT_DIR}/scraped_data.json")

    print_summary(all_results)

    elapsed = round(time.time() - start_time, 2)
    print(f"\nTotal time: {elapsed} seconds")

    if failures:
        print(f"\nFailures encountered:")
        for f in failures:
            print(f"  - {f}")


    return all_results
if __name__ == "__main__":
    run_pipeline()