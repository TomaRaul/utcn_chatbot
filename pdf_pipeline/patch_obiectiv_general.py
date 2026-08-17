import os
import re
import sys

import psycopg2
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB_CONFIG = {
    "host": "localhost", "port": 5432, "database": "chatbot_db",
    "user": "postgres", "password": os.getenv("DB_PASSWORD", ""),
}
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"
SOURCE = "obiectiv_general"

OBIECTIV_RE = re.compile(
    r"7\.1\s+Obiectivul\s+general\s+al\s+disciplinei\s*\n(.*?)(?=\n\s*7\.2\s+Obiectivele\s+specifice)",
    re.DOTALL | re.IGNORECASE,
)
DISCIPLINA_RE = re.compile(r"Disciplina:\s*(.+?)\.\s*\n", re.IGNORECASE)

def get_embedding(text):
    r = requests.post(OLLAMA_URL, json={"model": EMBEDDING_MODEL, "prompt": text}, timeout=120)
    r.raise_for_status()
    return r.json()["embedding"]

def fmt_vec(emb):
    return "[" + ",".join(map(str, emb)) + "]"

def strip_diacritics(s):
    return (
        s.replace("ă", "a").replace("â", "a").replace("î", "i")
         .replace("ș", "s").replace("ş", "s")
         .replace("ț", "t").replace("ţ", "t")
         .replace("Ă", "A").replace("Â", "A").replace("Î", "I")
         .replace("Ș", "S").replace("Ş", "S")
         .replace("Ț", "T").replace("Ţ", "T")
    )

def clean_obiectiv(text):
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("•", "").strip()
    return text

QUESTION_TEMPLATES = [
    "care este obiectivul general al disciplinei {N}",
    "care este obiectivul general la {N}",
    "care e obiectivul general la {N}",
    "care e obiectivul general pentru {N}",
    "care e obiectivul general pentru materia {N}",
    "care este obiectivul general pentru materia {N}",
    "care e obiectivul general al materiei {N}",
    "ce obiectiv general are {N}",
    "ce obiectiv general are disciplina {N}",
    "ce obiectiv general are materia {N}",
    "obiectivul general al disciplinei {N}",
    "obiectivul general la {N}",
    "obiectivul disciplinei {N}",
    "obiectivele disciplinei {N}",
    "ce urmareste materia {N}",
    "ce se invata la {N}",
    "ce se urmareste la cursul {N}",
    "scopul disciplinei {N}",
    "scopul cursului {N}",
    "care e scopul materiei {N}",
]

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("DELETE FROM knowledge_base WHERE source = %s", (SOURCE,))
    print(f"Sters {cur.rowcount} randuri vechi cu source='{SOURCE}'.")
    conn.commit()

    cur.execute(
        "SELECT source, answer FROM knowledge_base "
        "WHERE chunk_type='section' AND answer ILIKE %s",
        ("%Obiectivul general%",),
    )
    rows = cur.fetchall()
    print(f"Gasite {len(rows)} sectiuni candidate.")

    pairs = []
    skipped = 0
    for src, ans in rows:
        m_obj = OBIECTIV_RE.search(ans)
        m_disc = DISCIPLINA_RE.search(ans)
        if not m_obj or not m_disc:
            skipped += 1
            continue
        obiectiv = clean_obiectiv(m_obj.group(1))
        disciplina = m_disc.group(1).strip()
        if not obiectiv or not disciplina:
            skipped += 1
            continue

        answer = (
            f"Obiectivul general al disciplinei {disciplina}: {obiectiv}"
        )

        names = {disciplina, strip_diacritics(disciplina)}
        for n in names:
            for tpl in QUESTION_TEMPLATES:
                pairs.append((tpl.format(N=n), answer, src))

    print(f"Generate {len(pairs)} perechi Q&A (sarit {skipped} PDF-uri fara match).")

    inserted = 0
    for i, (q, a, pdf_src) in enumerate(pairs, 1):
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
        if inserted % 100 == 0:
            conn.commit()
            print(f"  inserate {inserted}/{len(pairs)}")
    conn.commit()
    cur.close()
    conn.close()
    print(f"Gata. Inserate {inserted} randuri cu source='{SOURCE}'.")

if __name__ == "__main__":
    main()
