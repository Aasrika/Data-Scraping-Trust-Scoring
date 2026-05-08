import re

MIN_CHUNK_LENGTH = 50    
MAX_CHUNK_LENGTH = 1000  
DEFAULT_CHUNK_SIZE = 200  

def chunk_by_paragraphs(text: str) -> list:
    if not text:
        return []

    raw_chunks = re.split(r'\n\s*\n', text.strip())

    chunks = []
    for chunk in raw_chunks:
        chunk = chunk.strip()

        # Skip chunks that are too short i.e likely noise
        if len(chunk) < MIN_CHUNK_LENGTH:
            continue

        # If chunk is too long, split it further by sentences
        if len(chunk) > MAX_CHUNK_LENGTH:
            sub_chunks = chunk_by_sentences(chunk)
            chunks.extend(sub_chunks)
        else:
            chunks.append(chunk)

    return chunks


def chunk_by_sentences(text: str, sentences_per_chunk: int = 4) -> list:
    if not text:
        return []
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    if not sentences:
        return []
    chunks = []
    for i in range(0, len(sentences), sentences_per_chunk):
        group = sentences[i:i + sentences_per_chunk]
        chunk = " ".join(group)
        if len(chunk) >= MIN_CHUNK_LENGTH:
            chunks.append(chunk)

    return chunks

def chunk_by_words(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = 20) -> list:
    if not text:
        return []

    words = text.split()

    if not words:
        return []

    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunk = " ".join(chunk_words)

        if len(chunk) >= MIN_CHUNK_LENGTH:
            chunks.append(chunk)

        step = chunk_size - overlap
        if step <= 0:
            step = chunk_size  # Prevent infinite loop if overlap >= chunk_size
        start += step

    return chunks

def chunk_content(text: str, source_type: str = "blog") -> list:
    if not text or len(text.strip()) < MIN_CHUNK_LENGTH:
        return [text.strip()] if text and text.strip() else []

    source_type = source_type.lower()

    if source_type == "youtube":
        # Transcripts are continuous — use sentence-based
        return chunk_by_sentences(text, sentences_per_chunk=4)

    elif source_type in ["blog", "pubmed"]:
        # Try paragraph-based first
        chunks = chunk_by_paragraphs(text)

        # Fallback: if we got fewer than 2 chunks, try sentence-based
        if len(chunks) < 2:
            chunks = chunk_by_sentences(text, sentences_per_chunk=4)

        # Final fallback: fixed-size if still not enough chunks
        if len(chunks) < 2:
            chunks = chunk_by_words(text)

        return chunks

    else:
        # Unknown source type then try paragraph first, then fall back
        chunks = chunk_by_paragraphs(text)
        if len(chunks) < 2:
            chunks = chunk_by_sentences(text)
        return chunks


def get_chunk_stats(chunks: list) -> dict:
    if not chunks:
        return {"count": 0, "avg_length": 0, "min_length": 0, "max_length": 0}

    lengths = [len(c) for c in chunks]
    return {
        "count": len(chunks),
        "avg_length": round(sum(lengths) / len(lengths)),
        "min_length": min(lengths),
        "max_length": max(lengths),
    }

if __name__ == "__main__":

    # Test 1: Blog post (paragraph-based)
    blog_text = """
    Machine learning has transformed how we approach data analysis.
    Algorithms can now detect patterns that would take humans years to find.

    Deep learning, a subset of machine learning, uses neural networks
    with many layers to learn representations of data. This has enabled
    breakthroughs in image recognition, speech processing, and NLP.

    Transformer models like BERT and GPT have particularly revolutionized
    natural language processing tasks. These models are pre-trained on
    massive text corpora and fine-tuned for specific downstream tasks.
    """

    blog_chunks = chunk_content(blog_text, source_type="blog")
    print("=== Blog Chunks ===")
    for i, chunk in enumerate(blog_chunks):
        print(f"Chunk {i+1}: {chunk[:80]}...")
    print("Stats:", get_chunk_stats(blog_chunks))
    print()

    # Test 2: YouTube transcript (sentence-based)
    transcript = "Welcome to this video on neural networks. Today we will cover the basics of backpropagation. Backpropagation is an algorithm used to train neural networks. It works by calculating the gradient of the loss function. These gradients tell us how to adjust the weights. After adjusting weights, we run the forward pass again. This process repeats until the model converges."

    yt_chunks = chunk_content(transcript, source_type="youtube")
    print("=== YouTube Chunks ===")
    for i, chunk in enumerate(yt_chunks):
        print(f"Chunk {i+1}: {chunk[:80]}...")
    print("Stats:", get_chunk_stats(yt_chunks))
    print()

    # Test 3: Fixed-size chunking
    long_text = " ".join(["word"] * 500)  # 500-word dummy text
    fixed_chunks = chunk_by_words(long_text, chunk_size=100, overlap=20)
    print("=== Fixed-Size Chunks ===")
    print(f"Total chunks: {len(fixed_chunks)}")
    print("Stats:", get_chunk_stats(fixed_chunks))