# Data Scraping & Trust Scoring Pipeline

A multi-source data scraping pipeline that collects structured content
from blogs, YouTube videos, and PubMed articles, and evaluates the
reliability of each source using a custom trust scoring algorithm.

## Project Structure

```
project/
├── main.py                    ← Run this to execute the full pipeline
├── requirements.txt           ← All dependencies
├── report_final.md            ← Short report explaining design decisions
├── .env.example               ← Template for required API keys
│
├── scraper/
│   ├── blog_scraper.py        ← Scrapes 3 blog posts
│   ├── youtube_scraper.py     ← Scrapes 2 YouTube videos
│   └── pubmed_scraper.py      ← Scrapes 1 PubMed article
│
├── scoring/
│   └── trust_score.py         ← 5-factor weighted trust scoring algorithm
│
├── utils/
│   ├── tagging.py             ← Automatic topic tag generation (KeyBERT)
│   └── chunking.py            ← Content chunking (paragraph/sentence/fixed)
│
└── output/
    ├── scraped_data.json      ← All 6 sources combined (main output)
    ├── blogs.json             ← 3 blog posts
    ├── youtube.json           ← 2 YouTube videos
    └── pubmed.json            ← 1 PubMed article
```

---

## Tools and Libraries Used

| Tool | Purpose | Why This Tool |
|---|---|---|
| `requests` | Fetches raw HTML from blog URLs | Lightweight, fast, no browser needed. Most blog content is in the initial HTML response so a full browser is unnecessary |
| `beautifulsoup4` + `lxml` | Parses HTML and extracts article content | BeautifulSoup provides a simple API for navigating HTML trees. lxml is the fastest parser and handles malformed HTML gracefully |
| `youtube-transcript-api` | Fetches YouTube video transcripts | The only library that retrieves plain-text transcripts directly from YouTube's caption service without needing a browser |
| `google-api-python-client` | Fetches YouTube video metadata | Official Google API client for YouTube Data API v3 — title, channel, publish date, description |
| `KeyBERT` | Automatic topic tag extraction | Uses BERT sentence embeddings to find semantically meaningful keywords rather than just frequent words |
| `sentence-transformers` | Sentence embeddings for KeyBERT | Provides the `all-MiniLM-L6-v2` model — lightweight (22MB), fast, high-quality embeddings |
| `langdetect` | Language detection | Google's language detection library — supports 55 languages, works offline, no API needed |
| `xml.etree.ElementTree` | XML parsing for PubMed API responses | Built into Python, no installation needed, purpose-built for clean XML |

---

## Scraping Approach

### Blogs
Uses `requests` to fetch raw HTML and `BeautifulSoup` with the `lxml`
parser to extract content. Before extracting article text, a two-pass
noise removal step strips navigation menus, footers, sidebars, ads, and
cookie banners. Content extraction follows a priority chain:

1. `<article>` tag — HTML5 semantic standard for article content
2. Common content div classes — `post-content`, `entry-content`, `article-body`
3. Largest `<div>` by text length — heuristic fallback for non-standard layouts
4. Full body text — last resort

Metadata (author, date) is extracted via JSON-LD structured data first,
then Open Graph meta tags, then HTML5 semantic attributes. This handles
different blog platforms without platform-specific code.

### YouTube
Requires two separate tools because no single library provides both
metadata and transcripts:

- **YouTube Data API v3** — fetches title, channel name, publish date,
  description, and tags via official Google API. Requires a free API key.
- **youtube-transcript-api** — fetches full video transcripts directly
  from YouTube's caption service. Manual captions are preferred over
  auto-generated ones for accuracy.

YouTube's frontend is JavaScript-rendered so BeautifulSoup alone cannot
parse it. The API-based approach bypasses this entirely.

### PubMed
Uses NCBI's free Entrez E-utilities API in two steps:

1. **ESearch** — searches PubMed by keyword and returns a list of PMIDs
2. **EFetch** — retrieves full article XML by PMID

Citation counts are fetched separately via the iCite API. XML responses
are parsed using Python's built-in `xml.etree.ElementTree`. A 0.4 second
delay is added between requests to stay within NCBI's rate limit of
3 requests per second.

---

## Trust Score Design

The trust score estimates source reliability on a scale of 0.0 to 1.0
using a weighted average of five independent factors:

```
Trust Score = 0.25 × author_credibility
            + 0.20 × citation_count
            + 0.25 × domain_authority
            + 0.20 × recency
            + 0.10 × medical_disclaimer
```

### Factor Breakdown

**Author Credibility (0.25)**
Checks whether the author name contains a known organization (Google,
NIH, Stanford, MIT, Anthropic, etc.). Known organization = 1.0, named
author present = 0.5, missing or anonymous = 0.1.

**Citation Count (0.20)**
Normalized as `min(citations / 100, 1.0)`. Defaults to neutral 0.5 for
blogs and YouTube since academic citations don't apply to those formats.

**Domain Authority (0.25)**
Hardcoded lookup table based on known domain reputation:
- `pubmed.ncbi.nlm.nih.gov` = 1.0
- `arxiv.org` = 0.90
- `blog.google` = 0.90
- `huggingface.co` = 0.80
- `medium.com` = 0.55
- Unknown domains = 0.40

**Recency (0.20)**
Tiered scoring based on content age:
- Under 6 months = 1.0
- 6–12 months = 0.8
- 1–2 years = 0.6
- 2–5 years = 0.4
- Over 5 years = 0.2
- Missing date = 0.3

**Medical Disclaimer (0.10)**
Only applies to content containing medical keywords. Medical content
with a disclaimer scores 1.0, medical content without a disclaimer
scores 0.0. Non-medical content defaults to 0.8.

### Weight Rationale
Author and domain together carry 50% because who published content and
where it was published are the strongest credibility signals. Recency
carries 20% because outdated information is a genuine trust risk.
Medical disclaimer carries only 10% since it is irrelevant for most
content types.

---

## Limitations

1. **Domain authority is hardcoded** — a production system would query
   the Moz or Ahrefs API for real domain authority scores on any URL.
   Unknown domains all default to 0.4 regardless of actual quality.

2. **Author verification is keyword-based** — the system checks for
   known organization names in the author field but cannot verify
   individual author identities.

3. **JavaScript-heavy sites may fail** — the pipeline uses requests +
   BeautifulSoup which cannot execute JavaScript. Heavily JS-rendered
   sites like Medium (behind login) return incomplete content.

4. **YouTube topic tags can be noisy** — transcripts are spoken language,
   which is less structured than written text. A minimum similarity
   threshold would filter low-quality tags.

5. **Citation count unavailable for blogs** — defaults to neutral 0.5.
   Social shares or backlinks could serve as proxy signals in a
   production system.

6. **Language detection unreliable on short text** — `langdetect` needs
   at least 20 characters to make a reliable detection.

7. **PubMed returns abstract only** — full article text requires a
   journal subscription. Trust scoring and topic tagging are based on
   the abstract alone.

---

## How to Run the Project

### 1. Clone the repository
```bash
git clone https://github.com/Aasrika/Data-Scraping-Trust-Scoring.git
cd Data-Scraping-Trust-Scoring
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up API keys
Add `.env`:
```
YOUTUBE_API_KEY=your_youtube_api_key_here
ENTREZ_EMAIL=your_email@example.com
```
### 4. Run the full pipeline
```bash
python main.py
```

Output files will be saved to the `output/` folder.

### 5. Run individual modules for testing
```bash
python scoring/trust_score.py    # Test trust scoring
python utils/tagging.py          # Test topic tagging
python utils/chunking.py         # Test content chunking
python scraper/pubmed_scraper.py # Test PubMed scraper
python scraper/blog_scraper.py   # Test blog scraper
python scraper/youtube_scraper.py # Test YouTube scraper
```

### Expected Output
Each source follows this JSON schema:
```json
{
  "source_url": "https://...",
  "source_type": "blog | youtube | pubmed",
  "author": "Author Name",
  "published_date": "YYYY-MM-DD",
  "language": "en",
  "region": "US | Global | N/A",
  "topic_tags": ["AI", "machine learning", "transformer model"],
  "trust_score": 0.742,
  "content_chunks": ["Paragraph 1...", "Paragraph 2...", "..."]
}
```
