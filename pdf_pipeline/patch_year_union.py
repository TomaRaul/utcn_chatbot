import os
import sys
import re
from collections import defaultdict

import psycopg2
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DB_CONFIG = {
    "host": "localhost", "port": 5432, "database": "chatbot_db",
    "user": "postgres", "password": os.getenv("DB_PASSWORD", ""),
}
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"
SOURCE = "year_union"

INT_TO_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}

def get_embedding(text):
    r = requests.post(OLLAMA_URL, json={"model": EMBEDDING_MODEL, "prompt": text}, timeout=120)
    r.raise_for_status()
    return r.json()["embedding"]

def fmt_vec(emb):
    return "[" + ",".join(map(str, emb)) + "]"

def is_clean_name(name):
    return bool(name) and len(name) >= 3

def aggregate(cur):
    cur.execute("SELECT DISTINCT source FROM knowledge_base WHERE source LIKE '%.pdf'")
    sources = [r[0] for r in cur.fetchall()]
    year_subjects = defaultdict(set)
    for src in sources:
        cur.execute("SELECT question, answer FROM knowledge_base WHERE source = %s", (src,))
        blob = "\n".join((q or "") + "\n" + (a or "") for q, a in cur.fetchall())
        m = re.search(r"Disciplina\s+(.+?)\s+are\s+\d+\s+credite", blob, re.IGNORECASE)
        if not m: continue
        name = m.group(1).strip().rstrip(".")
        if not is_clean_name(name):
            print(f"  [skip multi-name] {src}: {name[:80]}")
            continue
        m = re.search(r"studiaz[ăa]\s+(?:se\s+)?[îi]n\s+anul\s+([IViv]+|\d+)", blob, re.IGNORECASE)
        if not m: continue
        tok = m.group(1).lower()
        year = int(tok) if tok.isdigit() else {"i":1,"ii":2,"iii":3,"iv":4}.get(tok)
        if year is None: continue
        year_subjects[year].add(name)
    return year_subjects

QUESTION_TEMPLATES = [
    "zi mi toate materiile din anul {Y}",
    "zi-mi toate materiile din anul {Y}",
    "zi mi materiile din anul {Y}",
    "spune mi toate materiile din anul {Y}",
    "spune-mi toate materiile din anul {Y}",
    "spune mi toate materiile anul {Y}",
    "care sunt toate materiile din anul {Y}",
    "care sunt materiile din anul {Y}",
    "ce materii sunt in anul {Y}",
    "lista materii anul {Y}",
    "lista materiilor anul {Y}",
    "toate materiile anul {Y}",
    "toate materiile din anul {Y}",
    "materii anul {Y}",
    "ce materii are anul {Y}",
    "spune materiile anul {Y}",
    "enumera materiile din anul {Y}",
    "enumera toate materiile din anul {Y}",
    "ce se face in anul {Y}",
    "ce materii intra in anul {Y}",
]

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("DELETE FROM knowledge_base WHERE source = %s", (SOURCE,))
    print(f"Cleared {cur.rowcount} previous {SOURCE} rows.")
    conn.commit()

    year_subjects = aggregate(cur)
    print(f"Years aggregated: {sorted(year_subjects.keys())}")

    pairs = []
    for year, names_set in year_subjects.items():
        names = sorted(names_set, key=lambda s: s.lower())
        year_roman = INT_TO_ROMAN.get(year, str(year))
        year_arabic = str(year)
        bullets = "\n".join(f"- {n}" for n in names)
        listing = ", ".join(names)
        answer = (
            f"In anul {year_arabic} (anul {year_roman}) se studiaza in total "
            f"{len(names)} discipline:\n{bullets}"
        )
        for yr in (year_arabic, year_roman):
            for tpl in QUESTION_TEMPLATES:
                pairs.append((tpl.format(Y=yr), answer))

    print(f"Generated {len(pairs)} year-union Q&A pairs.")
    inserted = 0
    for i, (q, a) in enumerate(pairs, 1):
        try:
            emb = get_embedding(q + " " + a)
        except Exception as e:
            print(f"  [warn] embed fail #{i}: {e}")
            continue
        cur.execute(
            "INSERT INTO knowledge_base (question, answer, source, embedding, chunk_type, status) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (q, a, SOURCE, fmt_vec(emb), "qna", "active"),
        )
        inserted += 1
        if inserted % 25 == 0:
            conn.commit()
            print(f"  inserted {inserted}/{len(pairs)}")
    conn.commit()

    cur.execute(
        "DELETE FROM knowledge_base "
        "WHERE source = 'manifest_semestre' "
        "AND (answer ILIKE %s OR question ILIKE %s)",
        ("%Dezvoltare personală și profesională, Etică și integritate%",
         "%Dezvoltare personală%Etică%"),
    )
    print(f"Cleared {cur.rowcount} bad multi-subject manifest rows.")
    conn.commit()

    cur.close()
    conn.close()
    print(f"Done. Inserted {inserted} rows with source='{SOURCE}'.")

if __name__ == "__main__":
    main()
