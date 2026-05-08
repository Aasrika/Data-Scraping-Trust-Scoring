import requests
from bs4 import BeautifulSoup,Tag
import json
import os
import sys
import time
from urllib.parse import urlparse
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.tagging import generate_tags, detect_language
from utils.chunking import chunk_content
from scoring.trust_score import calculate_trust_score

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

REQUEST_DELAY = 1.5  
REQUEST_TIMEOUT = 15 

NOISE_TAGS = [
    "nav", "header", "footer", "aside", "script", "style",
    "noscript", "iframe", "form", "button", "advertisement",
    "cookie", "popup", "modal", "sidebar", "menu",
]

NOISE_CLASSES = [
    "nav", "navigation", "header", "footer", "sidebar", "menu",
    "advertisement", "ad", "ads", "cookie", "popup", "modal",
    "social", "share", "comment", "related", "recommended",
    "newsletter", "subscribe", "banner", "breadcrumb",
]

def fetch_html(url: str) -> BeautifulSoup | None:
    try:
        time.sleep(REQUEST_DELAY)
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        response.encoding = response.apparent_encoding

        soup = BeautifulSoup(response.text, "lxml")
        print(f"[Blog] Fetched: {url[:60]}...")
        return soup

    except requests.exceptions.Timeout:
        print(f"[Blog] Timeout for: {url}")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"[Blog] HTTP error {e.response.status_code} for: {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[Blog] Request failed for {url}: {e}")
        return None

def extract_title(soup: BeautifulSoup) -> str:
    # Strategy 1: h1 tag
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)

    # Strategy 2: Open Graph title
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()

    # Strategy 3: Twitter card title
    twitter_title = soup.find("meta", attrs={"name": "twitter:title"})
    if twitter_title and twitter_title.get("content"):
        return twitter_title["content"].strip()

    # Strategy 4: Page title tag
    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        return title_tag.get_text(strip=True)

    return "Unknown Title"


def extract_author(soup: BeautifulSoup) -> str:
    # Strategy 1: JSON-LD structured data (most reliable when present)
    # JSON-LD is a standard format for structured metadata
    # Google recommends it for SEO, so many blogs include it
    import json as json_module
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json_module.loads(script.string or "")            
            if isinstance(data, list):
                data = data[0]
            author = data.get("author", {})
            if isinstance(author, dict):
                name = author.get("name", "")
            elif isinstance(author, list):
                name = author[0].get("name", "") if author else ""
            elif isinstance(author, str):
                name = author
            else:
                name = ""
            if name:
                return name.strip()
        except Exception:
            continue

    # Strategy 2: Meta author tag
    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content"):
        return meta_author["content"].strip()

    # Strategy 3: rel="author" link
    rel_author = soup.find("a", rel="author")
    if rel_author and rel_author.get_text(strip=True):
        return rel_author.get_text(strip=True)

    # Strategy 4: Common author CSS classes
    for class_name in ["author", "byline", "post-author", "article-author", "writer"]:
        author_elem = soup.find(class_=class_name)
        if author_elem and author_elem.get_text(strip=True):
            text = author_elem.get_text(strip=True)
            text = text.replace("By ", "").replace("by ", "").strip()
            if len(text) < 60:  
                return text

    return "Unknown"

def extract_date(soup: BeautifulSoup) -> str:
    # Strategy 1: HTML5 time tag with datetime attribute
    time_tag = soup.find("time")
    if time_tag and time_tag.get("datetime"):
        return time_tag["datetime"][:10] 

    # Strategy 2: JSON-LD datePublished
    import json as json_module
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json_module.loads(script.string or "")
            if isinstance(data, list):
                data = data[0]
            date = data.get("datePublished", "")
            if date:
                return date[:10]
        except Exception:
            continue

    # Strategy 3: Open Graph article:published_time
    og_date = soup.find("meta", property="article:published_time")
    if og_date and og_date.get("content"):
        return og_date["content"][:10]

    # Strategy 4: Common date meta tags
    for name in ["date", "pubdate", "publishdate", "DC.date"]:
        meta_date = soup.find("meta", attrs={"name": name})
        if meta_date and meta_date.get("content"):
            return meta_date["content"][:10]

    return "Unknown"

def remove_noise(soup: BeautifulSoup) -> BeautifulSoup:
    # Pass 1: Remove noisy tags entirely
    for tag in NOISE_TAGS:
        for element in soup.find_all(tag):
            element.decompose()  # decompose() removes element and its children

    # Pass 2: Remove elements with noisy CSS classes or IDs
    for element in soup.find_all(True):
      if not isinstance(element, Tag):
        continue
    classes = element.get("class", [])
    element_id = element.get("id", "")

    class_str = " ".join(classes).lower()
    id_str = element_id.lower()

    if any(noise in class_str or noise in id_str for noise in NOISE_CLASSES):
        element.decompose()

    return soup


def extract_article_content(soup: BeautifulSoup) -> str:
    soup = remove_noise(soup)

    # Strategy 1: article tag
    article = soup.find("article")
    if article:
        return article.get_text(separator="\n\n", strip=True)

    # Strategy 2: Common content container classes
    content_classes = [
        "post-content", "entry-content", "article-content",
        "article-body", "post-body", "blog-content",
        "main-content", "content-body", "story-body",
        "post", "entry", "content"
    ]
    for class_name in content_classes:
        content = soup.find(class_=class_name)
        if content:
            text = content.get_text(separator="\n\n", strip=True)
            if len(text) > 200:  
                return text

    # Strategy 3: Find largest div by text content
    divs = soup.find_all("div")
    if divs:
        largest_div = max(divs, key=lambda d: len(d.get_text(strip=True)))
        text = largest_div.get_text(separator="\n\n", strip=True)
        if len(text) > 200:
            return text

    # Strategy 4: Full body text fallback
    body = soup.find("body")
    if body:
        return body.get_text(separator="\n\n", strip=True)

    return ""


def extract_region(soup: BeautifulSoup, url: str) -> str:
    # Strategy 1: HTML lang attribute
    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        lang = html_tag["lang"]
        if "-" in lang:
            return lang.split("-")[1].upper()  

    # Strategy 2: OG locale
    og_locale = soup.find("meta", property="og:locale")
    if og_locale and og_locale.get("content"):
        locale = og_locale["content"]
        if "_" in locale:
            return locale.split("_")[1].upper()  

    # Strategy 3: TLD from URL
    tld_region_map = {
        ".in": "India",".co.uk": "UK", ".uk": "UK",".ca": "Canada", ".au": "Australia",".de": "Germany",".fr": "France", ".jp": "Japan" }
    for tld, region in tld_region_map.items():
        if tld in url:
            return region

    return "Global"

def scrape_blog_post(url: str) -> dict:
    print(f"\n[Blog] Scraping: {url}")
    # Step 1: Fetch HTML
    soup = fetch_html(url)
    if soup is None:
        return {}

    # Step 2: Extract metadata
    title        = extract_title(soup)
    author       = extract_author(soup)
    published    = extract_date(soup)
    region       = extract_region(soup, url)

    # Step 3: Extract content
    content = extract_article_content(soup)
    if not content:
        print(f"[Blog] Could not extract content from: {url}")
        return {}

    # Step 4: Language detection
    language = detect_language(content)

    # Step 5: Topic tagging
    full_text_for_tags = f"{title} {content}"
    tags = generate_tags(full_text_for_tags)

    # Step 6: Content chunking
    chunks = chunk_content(content, source_type="blog")

    # Step 7: Trust score
    trust_result = calculate_trust_score(
        url=url,
        author=author,
        published_date=published,
        content=content,
        citation_count=None,
        source_type="blog"
    )

    # Step 8: Assemble result
    result = {
        "source_url":      url,
        "source_type":     "blog",
        "author":          author,
        "published_date":  published,
        "language":        language,
        "region":          region,
        "topic_tags":      tags,
        "trust_score":     trust_result["trust_score"],
        "content_chunks":  chunks,
        "_title":           title,
        "_trust_breakdown": trust_result["factor_breakdown"],
        "_content_length":  len(content),
        "_chunk_count":     len(chunks),
    }

    print(f"[Blog] Title: {title[:60]}...")
    print(f"[Blog] Author: {author}")
    print(f"[Blog] Trust score: {trust_result['trust_score']}")
    print(f"[Blog] Tags: {tags[:5]}")
    print(f"[Blog] Chunks: {len(chunks)}")

    return result


def scrape_multiple_blogs(urls: list) -> list:
    results = []
    for url in urls:
        result = scrape_blog_post(url)
        if result:
            results.append(result)
        else:
            print(f"[Blog] Skipping failed URL: {url}")
    return results

def save_to_json(data: list, filepath: str = "output/blogs.json"):
    """Saves list of scraped blog posts to JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n[Blog] Saved {len(data)} posts to {filepath}")

if __name__ == "__main__":

    BLOG_URLS = [
    "https://huggingface.co/blog/rlhf",
    "https://huggingface.co/blog/introduction-to-ggml",
    "https://huggingface.co/blog/llama2",
]

    results = scrape_multiple_blogs(BLOG_URLS)

    if results:
        save_to_json(results, "output/blogs.json")
        print(f"\n SUMMARY")
        for r in results:
            print(f"URL: {r['source_url'][:50]}...")
            print(f"  Author: {r['author']}")
            print(f"  Date: {r['published_date']}")
            print(f"  Trust: {r['trust_score']}")
            print(f"  Tags: {r['topic_tags'][:3]}")
            print()