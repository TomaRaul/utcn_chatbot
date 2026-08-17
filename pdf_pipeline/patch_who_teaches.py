import os
import sys
import re
from collections import defaultdict

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
SOURCE = "who_teaches"

def get_embedding(text):
    r = requests.post(OLLAMA_URL, json={"model": EMBEDDING_MODEL, "prompt": text}, timeout=120)
    r.raise_for_status()
    return r.json()["embedding"]

def fmt_vec(emb):
    return "[" + ",".join(map(str, emb)) + "]"

def collect_profs(cur):
    cur.execute("SELECT DISTINCT source FROM knowledge_base WHERE source LIKE '%.pdf'")
    sources = [r[0] for r in cur.fetchall()]
    out = {}
    for src in sources:
        cur.execute(
            "SELECT answer FROM knowledge_base "
            "WHERE source = %s AND answer ILIKE %s LIMIT 1",
            (src, "Titularii de curs%"),
        )
        r = cur.fetchone()
        if not r:
            continue
        ans = r[0]
        m = re.search(r"disciplinei\s+(.+?)\s+sunt:", ans)
        if not m:
            continue
        name = m.group(1).strip()
        out[src] = (name, ans)
    return out

QUESTION_TEMPLATES = [
    "cine preda {N}",
    "cine preda {N}?",
    "cine predă {N}",
    "cine predă {N}?",
    "cine tine cursul la {N}",
    "cine tine cursul la {N}?",
    "cine ține cursul la {N}",
    "cine sustine cursul la {N}",
    "cine este profesor la {N}",
    "cine e profesor la {N}",
    "cine este titularul disciplinei {N}",
    "cine este titularul la {N}",
    "cine sunt profesorii la {N}",
    "cine sunt profesorii de la {N}",
    "cine face cursul la {N}",
    "cine face cursul la {N}?",
    "ce profesor preda {N}",
    "ce profesor preda {N}?",
    "ce profesor tine {N}",
    "cine este cadru didactic la {N}",
    "cine ține {N}",
    "profesorul de la {N}",
    "titularul de la {N}",
    "titularii cursului {N}",
    "cine preda materia {N}",
    "cine preda disciplina {N}",
]

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("DELETE FROM knowledge_base WHERE source = %s", (SOURCE,))
    print(f"Cleared {cur.rowcount} previous {SOURCE} rows.")
    conn.commit()

    profs = collect_profs(cur)
    print(f"Found prof Q&A for {len(profs)} disciplines.")

    pairs = []
    for src, (name, answer) in profs.items():
        ascii_name = (
            name.replace("ă", "a").replace("â", "a").replace("î", "i")
            .replace("ș", "s").replace("ş", "s")
            .replace("ț", "t").replace("ţ", "t")
            .replace("Ă", "A").replace("Â", "A").replace("Î", "I")
            .replace("Ș", "S").replace("Ş", "S")
            .replace("Ț", "T").replace("Ţ", "T")
        )
        names = {name, ascii_name}
        for n in names:
            for tpl in QUESTION_TEMPLATES:
                pairs.append((tpl.format(N=n), answer))

    print(f"Generated {len(pairs)} 'who teaches' Q&A pairs.")
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
        if inserted % 50 == 0:
            conn.commit()
            print(f"  inserted {inserted}/{len(pairs)}")
    conn.commit()
    cur.close()
    conn.close()
    print(f"Done. Inserted {inserted} rows with source='{SOURCE}'.")

if __name__ == "__main__":
    main()
