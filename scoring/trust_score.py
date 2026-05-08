from datetime import datetime, timezone
from urllib.parse import urlparse

WEIGHTS = {
    "author_credibility":        0.25,  
    "citation_count":            0.20,  
    "domain_authority":          0.25,  
    "recency":                   0.20,  
    "medical_disclaimer":        0.10,  
}


DOMAIN_AUTHORITY_SCORES = {
    "pubmed.ncbi.nlm.nih.gov":  1.00,  
    "nature.com":               0.95,  
    "arxiv.org":                0.90,  
    "ieee.org":                 0.90,  
    "towardsdatascience.com":   0.75,  
    "medium.com":               0.55,  
    "youtube.com":              0.60,  
    "blogger.com":              0.35,  
    "blogspot.com":             0.30,  
    "wordpress.com":            0.35,  
    "huggingface.co":           0.80,
    "blog.google":              0.90,
}

DEFAULT_DOMAIN_SCORE = 0.4

KNOWN_ORGANIZATIONS = [
    "google", "deepmind", "openai", "meta", "microsoft",
    "stanford", "mit", "harvard", "oxford", "cambridge",
    "nih", "who", "cdc", "nature", "ieee", "acm",
    "nvidia", "anthropic", "hugging face", "huggingface",
]

MEDICAL_KEYWORDS = [
    "diagnosis", "treatment", "medication", "clinical", "patient",
    "disease", "symptom", "therapy", "drug", "dosage", "medical",
    "health", "hospital", "surgery", "vaccine", "prescription",
]


def score_author_credibility(author: str) -> float:   
    if not author or author.strip().lower() in ["", "unknown", "admin", "staff", "anonymous"]:
        return 0.1

    author_lower = author.lower()
    for org in KNOWN_ORGANIZATIONS:
        if org in author_lower:
            return 1.0  

    return 0.5 

def score_multiple_authors(authors: list) -> float:    
    if not authors:
        return 0.1
    scores = [score_author_credibility(a) for a in authors]
    return round(sum(scores) / len(scores), 4)

def score_citation_count(citation_count, source_type: str = "blog") -> float:
    if source_type != "pubmed":
        return 0.5  

    if citation_count is None:
        return 0.3  

    return round(min(citation_count / 100, 1.0), 4)

def score_domain_authority(url: str) -> float:
    if not url:
        return DEFAULT_DOMAIN_SCORE

    try:
        domain = urlparse(url).netloc  
        domain = domain.replace("www.", "")
        return DOMAIN_AUTHORITY_SCORES.get(domain, DEFAULT_DOMAIN_SCORE)
    except Exception:
        return DEFAULT_DOMAIN_SCORE

def score_recency(published_date: str) -> float:
    if not published_date:
        return 0.3  

    try:
        
        formats = [
            "%Y-%m-%d",        # 2026-05-08 
            "%B %d, %Y",       # May 8, 2026 
            "%d %B %Y",        # May 8, 2026
            "%Y/%m/%d",        # 2026/05/08
            "%Y",              # 2026  
        ]

        parsed_date = None
        for fmt in formats:
            try:
                parsed_date = datetime.strptime(published_date.strip(), fmt)
                break  
            except ValueError:
                continue

        if parsed_date is None:
            return 0.3  
        now = datetime.now()
        age_days = (now - parsed_date).days

        if age_days < 180:    return 1.0   
        elif age_days < 365:  return 0.8   
        elif age_days < 730:  return 0.6   
        elif age_days < 1825: return 0.4   
        else:                 return 0.2   

    except Exception:
        return 0.3

def score_medical_disclaimer(content: str) -> float:
    if not content:
        return 0.5  

    content_lower = content.lower()
    is_medical = any(keyword in content_lower for keyword in MEDICAL_KEYWORDS)

    if not is_medical:
        return 0.8  

    disclaimer_phrases = [
        "consult a doctor",
        "consult your physician",
        "not medical advice",
        "seek professional advice",
        "this is not a substitute",
        "talk to your doctor",
        "medical professional",
        "healthcare provider",
        "for informational purposes only",
    ]

    has_disclaimer = any(phrase in content_lower for phrase in disclaimer_phrases)

    return 1.0 if has_disclaimer else 0.0

def calculate_trust_score(
    url: str,
    author,              
    published_date: str,
    content: str,
    citation_count=None,
    source_type: str = "blog"
) -> dict:
    
   
    if isinstance(author, list):
        author_score = score_multiple_authors(author)
    else:
        author_score = score_author_credibility(author)

    factors = {
        "author_credibility":   author_score,
        "citation_count":       score_citation_count(citation_count, source_type),
        "domain_authority":     score_domain_authority(url),
        "recency":              score_recency(published_date),
        "medical_disclaimer":   score_medical_disclaimer(content),
    }

    final_score = sum(WEIGHTS[factor] * score for factor, score in factors.items())
    final_score = round(final_score, 3)

    return {
        "trust_score": final_score,
        "factor_breakdown": {k: round(v, 3) for k, v in factors.items()}
    }


if __name__ == "__main__":

    # Test Case 1: High-trust PubMed article
    result1 = calculate_trust_score(
        url="https://pubmed.ncbi.nlm.nih.gov/12345678/",
        author=["Dr. John Smith", "NIH Research Team"],
        published_date="2024-08-15",
        content="This study examines clinical treatment options. Consult a doctor before use.",
        citation_count=85,
        source_type="pubmed"
    )
    print("PubMed Article:", result1)

    # Test Case 2: Low-trust anonymous blog
    result2 = calculate_trust_score(
        url="https://randomhealth.blogspot.com/post",
        author="Admin",
        published_date="2018-03-01",
        content="This medication cures everything! Take 500mg daily for best results.",
        citation_count=None,
        source_type="blog"
    )
    print("Suspicious Blog:", result2)

    # Test Case 3: YouTube video
    result3 = calculate_trust_score(
        url="https://www.youtube.com/watch?v=abc123",
        author="Google DeepMind",
        published_date="2024-11-20",
        content="In this video we explain our latest AI research on large language models.",
        citation_count=None,
        source_type="youtube"
    )
    print("YouTube Video:", result3)