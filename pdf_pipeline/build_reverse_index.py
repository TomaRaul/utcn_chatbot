import os
import re
import sys
import requests
import psycopg2
from collections import defaultdict
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "chatbot_db",
    "user": "postgres",
    "password": os.getenv("DB_PASSWORD", "")
}

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"

TITLE_TOKEN = re.compile(
    r"^(Prof\.?|Conf\.?|Lect\.?|Lector|As\.?|Asist\.?|Asistent|Şl\.?|Șl\.?|Dr\.?|univ\.?|dr\.?|ing\.?|mat\.?)$",
    re.IGNORECASE
)
NAME_EMAIL_RE = re.compile(
    r"((?:Prof|Conf|Lect|Lector|As|Asist|Asistent|Şl|Șl)\.?[^\n-]*?)\s*-\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+)"
)

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def get_embedding(text):
    r = requests.post(OLLAMA_URL, json={"model": EMBEDDING_MODEL, "prompt": text}, timeout=60)
    r.raise_for_status()
    return r.json()["embedding"]

def format_vector(emb):
    return "[" + ",".join(map(str, emb)) + "]"

def clean_name(full):
    s = re.sub(r"\s*\([^)]*\)\s*", " ", full).strip()
    tokens = re.split(r"\s+", s)
    cleaned = [t for t in tokens if not TITLE_TOKEN.match(t.strip("."))]
    return " ".join(cleaned).strip()

def last_name(name):
    parts = name.split()
    return parts[-1] if parts else name

def normalize_email(email):
    return email.strip().strip(".").lower()

def parse_answer(answer):
    disc_match = re.search(r"ai\s+disciplinei\s+(.+?)\s+sunt\s*:", answer, re.IGNORECASE)
    discipline = disc_match.group(1).strip() if disc_match else None
    pairs = NAME_EMAIL_RE.findall(answer)
    pairs = [(p[0].strip(), normalize_email(p[1])) for p in pairs]
    return discipline, pairs

def build_index(cur):
    cur.execute("""
        SELECT DISTINCT ON (source, answer) source, answer
        FROM knowledge_base
        WHERE chunk_type = 'qna'
          AND (status IS NULL OR status = 'active')
          AND question LIKE 'Cine predă %'
    """)
    rows = cur.fetchall()
    log(f"Scanning {len(rows)} forward 'Cine predă X?' Q&As.")

    by_email = defaultdict(lambda: {"name_full": None, "disciplines": set()})
    for source, answer in rows:
        discipline, pairs = parse_answer(answer)
        if not discipline or not pairs:
            continue
        for full_title_name, email in pairs:
            entry = by_email[email]
            if entry["name_full"] is None or len(full_title_name) > len(entry["name_full"]):
                entry["name_full"] = full_title_name
            entry["disciplines"].add(discipline)

    return by_email

def reverse_questions(name_clean, last):
    qs = [
        f"Ce predă {name_clean}?",
        f"Ce materii predă {name_clean}?",
        f"Ce discipline predă {name_clean}?",
        f"La ce discipline predă {name_clean}?",
        f"Care sunt cursurile lui {name_clean}?",
        f"Ce cursuri ține {name_clean}?",
    ]
    if last and last != name_clean:
        qs += [
            f"Ce predă {last}?",
            f"Ce materii predă {last}?",
            f"Care sunt cursurile lui {last}?",
        ]
    return qs

def build_answer(name_full, disciplines):
    if not disciplines:
        return None
    if len(disciplines) == 1:
        return f"{name_full} predă disciplina {next(iter(disciplines))}."
    listed = ", ".join(sorted(disciplines))
    return f"{name_full} predă următoarele discipline: {listed}."

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("DELETE FROM knowledge_base WHERE source = 'reverse-index'")
    deleted = cur.rowcount
    log(f"Cleared {deleted} previous reverse-index rows.")

    by_email = build_index(cur)
    log(f"Aggregated {len(by_email)} unique teachers across the catalogue.")

    inserted = 0
    for email, info in by_email.items():
        name_full = info["name_full"]
        disciplines = info["disciplines"]
        if not name_full or not disciplines:
            continue
        name_clean = clean_name(name_full)
        if not name_clean:
            continue
        last = last_name(name_clean)
        answer = build_answer(name_full, disciplines)

        for q in reverse_questions(name_clean, last):
            try:
                emb = get_embedding(f"{q} {answer}")
                cur.execute("""
                    INSERT INTO knowledge_base
                        (question, answer, source, embedding, chunk_type, status, quality_score)
                    VALUES (%s, %s, 'reverse-index', %s, 'qna', 'active', 0)
                """, (q, answer, format_vector(emb)))
                inserted += 1
            except Exception as e:
                log(f"  embed/insert failed for '{q}': {e}")
        conn.commit()

    log(f"Inserted {inserted} reverse-index Q&A rows.")
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
