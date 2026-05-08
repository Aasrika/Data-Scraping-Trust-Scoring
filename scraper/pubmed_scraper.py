import requests
import xml.etree.ElementTree as ET
import time
import json
import os
import sys


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.tagging import generate_tags, detect_language
from utils.chunking import chunk_content
from scoring.trust_score import calculate_trust_score
from dotenv import load_dotenv
import os
load_dotenv()
ENTREZ_EMAIL = os.getenv("ENTREZ_EMAIL")

ENTREZ_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

REQUEST_DELAY = 0.4

def search_pubmed(query: str, max_results: int = 5) -> list:
    params = {
        "db": "pubmed",        
        "term": query,         
        "retmax": max_results, 
        "retmode": "json",     
        "email": ENTREZ_EMAIL,
    }

    try:
        response = requests.get(
            f"{ENTREZ_BASE_URL}esearch.fcgi",
            params=params,
            timeout=10  
        )
        response.raise_for_status()  
        data = response.json()
        pmids = data.get("esearchresult", {}).get("idlist", [])
        print(f"[PubMed] Found {len(pmids)} articles for query: '{query}'")
        return pmids

    except requests.exceptions.RequestException as e:
        print(f"[PubMed] Search failed: {e}")
        return []

def fetch_pubmed_article(pmid: str) -> dict:
    params = {
        "db": "pubmed",
        "id": pmid,
        "retmode": "xml",  
        "rettype": "abstract",
        "email": ENTREZ_EMAIL,
    }

    try:
        time.sleep(REQUEST_DELAY)  

        response = requests.get(
            f"{ENTREZ_BASE_URL}efetch.fcgi",
            params=params,
            timeout=15
        )
        response.raise_for_status()

        root = ET.fromstring(response.content)
        article = root.find(".//PubmedArticle")
        if article is None:
            print(f"[PubMed] No article found for PMID: {pmid}")
            return {}

        title_elem = article.find(".//ArticleTitle")
        title = title_elem.text if title_elem is not None else "Unknown Title"

        authors = []
        for author in article.findall(".//Author"):
            last = author.findtext("LastName", "")
            fore = author.findtext("ForeName", "")
            full_name = f"{fore} {last}".strip()
            if full_name:
                authors.append(full_name)

        journal_elem = article.find(".//Journal/Title")
        journal = journal_elem.text if journal_elem is not None else "Unknown Journal"

        year = (
            article.findtext(".//PubDate/Year") or
            article.findtext(".//ArticleDate/Year") or
            article.findtext(".//DateCompleted/Year") or
            "Unknown"
        )

        abstract_texts = []
        for abstract_text in article.findall(".//AbstractText"):
            label = abstract_text.get("Label", "")
            text = abstract_text.text or ""
            if label:
                abstract_texts.append(f"{label}: {text}")
            else:
                abstract_texts.append(text)

        abstract = " ".join(abstract_texts) if abstract_texts else "No abstract available"


        citation_count = fetch_citation_count(pmid)

        return {
            "pmid": pmid,
            "title": title,
            "authors": authors,
            "journal": journal,
            "year": year,
            "abstract": abstract,
            "citation_count": citation_count,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        }

    except ET.ParseError as e:
        print(f"[PubMed] XML parse error for PMID {pmid}: {e}")
        return {}
    except requests.exceptions.RequestException as e:
        print(f"[PubMed] Fetch failed for PMID {pmid}: {e}")
        return {}


def fetch_citation_count(pmid: str) -> int:
    try:
        time.sleep(REQUEST_DELAY)
        response = requests.get(
            f"https://icite.od.nih.gov/api/pubs?pmids={pmid}",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        pubs = data.get("data", [])
        if pubs:
            return pubs[0].get("citation_count", 0)
        return 0
    except Exception:
        return 0  

def scrape_pubmed_article(query: str = "machine learning cancer detection") -> dict:
    print(f"\n[PubMed] Scraping article for query: '{query}'")

    # Step 1: Search
    pmids = search_pubmed(query, max_results=3)
    if not pmids:
        print("[PubMed] No results found.")
        return {}

    # Step 2: Fetch first article
    article_data = {}
    for pmid in pmids:
        article_data = fetch_pubmed_article(pmid)
        if article_data:
            break  

    if not article_data:
        print("[PubMed] Could not fetch article data.")
        return {}

    abstract = article_data.get("abstract", "")
    authors  = article_data.get("authors", [])
    year     = article_data.get("year", "")
    url      = article_data.get("url", "")

    # Step 3: Language detection
    language = detect_language(abstract)

    # Step 4: Topic tagging
    full_text = f"{article_data.get('title', '')} {abstract}"
    tags = generate_tags(full_text)

    # Step 5: Content chunking
    # PubMed abstracts are short — sentence-based chunking works best
    chunks = chunk_content(abstract, source_type="pubmed")

    # Step 6: Trust score
    trust_result = calculate_trust_score(
        url=url,
        author=authors,
        published_date=year,
        content=abstract,
        citation_count=article_data.get("citation_count"),
        source_type="pubmed"
    )

    # Step 7: Assemble final JSON object
    result = {
        "source_url":      url,
        "source_type":     "pubmed",
        "author":          ", ".join(authors) if authors else "Unknown",
        "published_date":  year,
        "language":        language,
        "region":          "N/A",  # PubMed doesn't provide region data
        "topic_tags":      tags,
        "trust_score":     trust_result["trust_score"],
        "content_chunks":  chunks,
        # Extra fields for context (not in schema but useful)
        "_title":          article_data.get("title", ""),
        "_journal":        article_data.get("journal", ""),
        "_pmid":           article_data.get("pmid", ""),
        "_citation_count": article_data.get("citation_count", 0),
        "_trust_breakdown": trust_result["factor_breakdown"]
    }

    print(f"[PubMed] Successfully scraped: {article_data.get('title', '')[:60]}...")
    print(f"[PubMed] Trust score: {trust_result['trust_score']}")
    print(f"[PubMed] Tags: {tags}")

    return result

def save_to_json(data: dict, filepath: str = "output/pubmed.json"):
    """Saves scraped data to a JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[PubMed] Saved to {filepath}")

if __name__ == "__main__":
    result = scrape_pubmed_article(
        query="machine learning natural language processing evaluation"
    )
    if result:
        save_to_json(result, "output/pubmed.json")
        print("\n=== OUTPUT PREVIEW ===")
        preview = {k: v for k, v in result.items() if not k.startswith("_")}
        print(json.dumps(preview, indent=2))