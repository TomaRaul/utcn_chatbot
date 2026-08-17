import os
import sys
import math
import re
import unicodedata
import requests
import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "chatbot_db",
    "user": "postgres",
    "password": os.getenv("DB_PASSWORD", "")
}

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"

KEYWORD_BOOST_PER_MATCH = 0.07
KEYWORD_BOOST_MAX = 0.25
QNA_BOOST = 0.15
SOURCE_MATCH_BOOST = 0.30

STOPWORDS = {
    "care", "este", "sunt", "cine", "cand", "unde", "ce", "cum", "de", "la", "cu",
    "in", "pe", "si", "sau", "dar", "din", "pentru", "despre", "ai", "are",
    "fie", "fara", "spune", "imi", "tu", "tine",
    "vrea", "stii", "stie",
    "the", "what", "who", "where", "when", "how", "does",
    "facultate", "facultatea", "universitate", "universitatea"
}

def normalize(text):
    if not text:
        return ""
    lower = text.lower()
    stripped = unicodedata.normalize("NFD", lower)
    stripped = "".join(c for c in stripped if unicodedata.category(c) != "Mn")
    return stripped

def extract_keywords(text):
    norm = normalize(text)
    out = set()
    for tok in re.split(r"\s+", norm):
        clean = re.sub(r"[^a-z0-9]", "", tok)
        if clean and len(clean) >= 3 and clean not in STOPWORDS:
            out.add(clean)
    return out

def keyword_boost(query_keywords, q, a):
    haystack = normalize((q or "") + " " + (a or ""))
    matches = sum(1 for k in query_keywords if k in haystack)
    return min(matches * KEYWORD_BOOST_PER_MATCH, KEYWORD_BOOST_MAX)

def tokenize_source(source):
    if not source:
        return set()
    stem = re.sub(r"\.[^.]+$", "", source)
    split = re.sub(r"([a-z])([A-Z])", r"\1 \2", stem)
    split = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", split)
    split = re.sub(r"[_\d]", " ", split)
    out = set()
    for tok in split.split():
        n = re.sub(r"[^a-z0-9]", "", normalize(tok))
        if len(n) >= 3:
            out.add(n)
    return out

def get_embedding(text):
    r = requests.post(OLLAMA_URL, json={"model": EMBEDDING_MODEL, "prompt": text}, timeout=60)
    r.raise_for_status()
    return r.json()["embedding"]

def parse_vector(s):
    s = s.strip().strip("[]")
    return [float(x) for x in s.split(",")]

def cosine(a, b):
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)

def main():
    query = " ".join(sys.argv[1:]) or "cine preda programarea calculatoarelor"
    print(f"Query: {query}\n")
    qe = get_embedding(query)
    keywords = extract_keywords(query)
    print(f"Query keywords (after stopword removal): {keywords}\n")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT id, source, question, answer, embedding, chunk_type FROM knowledge_base WHERE embedding IS NOT NULL")
    rows = cur.fetchall()

    source_tokens_cache = {}
    matching_sources = set()
    for _, source, _, _, _, _ in rows:
        if source and source not in source_tokens_cache:
            source_tokens_cache[source] = tokenize_source(source)
    for source, toks in source_tokens_cache.items():
        if toks and (toks & keywords):
            matching_sources.add(source)
    print(f"Matching sources (token overlap with query): {sorted(matching_sources)}\n")

    scored = []
    for id_, source, q, a, emb, ctype in rows:
        sim = cosine(qe, parse_vector(emb))
        kb = keyword_boost(keywords, q, a)
        qb = QNA_BOOST if ctype == "qna" else 0
        sb = SOURCE_MATCH_BOOST if source in matching_sources else 0
        total = sim + kb + qb + sb
        scored.append((total, sim, kb, qb, sb, id_, source, q, a, ctype))

    scored.sort(reverse=True, key=lambda x: x[0])

    print(f"Top 10 by total score (cosine + kw + qna + src), out of {len(scored)} entries:\n")
    for i, (total, sim, kb, qb, sb, id_, source, q, a, ctype) in enumerate(scored[:10], 1):
        snippet = a[:200].replace("\n", " ")
        print(f"#{i}  total={total:.4f}  cos={sim:.4f}  kw={kb:.2f}  qna={qb:.2f}  src={sb:.2f}  [{source}] type={ctype} id={id_}")
        print(f"    Q: {q}")
        print(f"    A: {snippet}")
        print()

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
