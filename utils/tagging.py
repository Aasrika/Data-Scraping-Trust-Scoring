from keybert import KeyBERT
from langdetect import detect, LangDetectException

kw_model = KeyBERT(model="all-MiniLM-L6-v2")

TOPIC_CATEGORIES = {
    "AI": [
        "artificial intelligence", "ai", "machine learning", "deep learning",
        "neural network", "nlp", "natural language processing", "computer vision",
        "reinforcement learning", "transformer", "llm", "large language model",
        "generative ai", "rag", "retrieval augmented"
    ],
    "Healthcare": [
        "medical", "health", "clinical", "patient", "disease", "treatment",
        "diagnosis", "drug", "hospital", "surgery", "vaccine", "cancer",
        "mental health", "medication", "therapy"
    ],
    "Data Science": [
        "data science", "data analysis", "statistics", "visualization",
        "pandas", "numpy", "dataset", "exploratory", "feature engineering",
        "regression", "classification", "clustering"
    ],
    "Research": [
        "research", "study", "paper", "journal", "publication", "experiment",
        "hypothesis", "methodology", "findings", "results", "analysis",
        "peer review", "citation", "abstract"
    ],
    "Technology": [
        "software", "programming", "python", "javascript", "api",
        "cloud", "database", "web", "mobile", "security", "blockchain",
        "iot", "robotics", "automation"
    ],
    "Education": [
        "learning", "education", "course", "tutorial", "training",
        "student", "university", "school", "curriculum", "skill"
    ],
    "Business": [
        "business", "startup", "revenue", "market", "product",
        "strategy", "management", "enterprise", "investment", "growth"
    ],
    "Environment": [
        "environment", "climate", "sustainability", "energy", "carbon",
        "renewable", "pollution", "ecosystem", "green", "waste"
    ],
}


def detect_language(text: str) -> str:
    if not text or len(text.strip()) < 20:
        return "unknown"  
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"

def extract_keywords(text: str, top_n: int = 10) -> list:
    if not text or len(text.strip()) < 50:
        return []  
    text_sample = text[:5000]

    try:
        keywords = kw_model.extract_keywords(
            text_sample,
            keyphrase_ngram_range=(1, 2),
            stop_words="english",
            use_maxsum=True,
            diversity=0.5,
            top_n=top_n
        )
        
        return [kw for kw, score in keywords]

    except Exception as e:
        print(f"[tagging] Keyword extraction failed: {e}")
        return []

def map_to_topic_categories(keywords: list) -> list:
    matched_categories = set()  

    for keyword in keywords:
        keyword_lower = keyword.lower()
        for category, category_keywords in TOPIC_CATEGORIES.items():
            # Check if extracted keyword matches any category keyword
            if any(cat_kw in keyword_lower or keyword_lower in cat_kw
                   for cat_kw in category_keywords):
                matched_categories.add(category)

    return list(matched_categories)

def generate_tags(text: str, top_n: int = 10) -> list:
    if not text:
        return []
    keywords = extract_keywords(text, top_n=top_n)
    categories = map_to_topic_categories(keywords)
    all_tags = list(dict.fromkeys(categories + keywords))  

    return all_tags[:10] 


if __name__ == "__main__":

    # Test 1: AI/ML content
    sample_text = """
    Large language models (LLMs) have revolutionized natural language processing.
    Transformer architectures with attention mechanisms allow models to understand
    context across long sequences. Fine-tuning pre-trained models like BERT and GPT
    on domain-specific data has shown remarkable results in question answering,
    text summarization, and sentiment analysis tasks.
    """
    tags = generate_tags(sample_text)
    print("AI/ML Tags:", tags)

    # Test 2: Medical content
    medical_text = """
    Recent clinical trials have shown promising results for the treatment of
    Type 2 diabetes using a combination of medication and lifestyle interventions.
    Patients showed significant improvement in blood glucose levels after 12 weeks.
    Always consult your doctor before making changes to your treatment plan.
    """
    tags2 = generate_tags(medical_text)
    print("Medical Tags:", tags2)

    # Test 3: Language detection
    hindi_text = "मशीन लर्निंग एक कृत्रिम बुद्धिमत्ता की शाखा है।"
    print("Detected language:", detect_language(hindi_text))
    print("Detected language (English):", detect_language(sample_text))