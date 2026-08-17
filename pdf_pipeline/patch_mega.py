import os
import sys
import re

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
SOURCE = "all_facts"

def get_embedding(text):
    r = requests.post(OLLAMA_URL, json={"model": EMBEDDING_MODEL, "prompt": text}, timeout=120)
    r.raise_for_status()
    return r.json()["embedding"]

def fmt_vec(emb):
    return "[" + ",".join(map(str, emb)) + "]"

def strip_diacritics(s):
    return (s.replace("ă", "a").replace("â", "a").replace("î", "i")
             .replace("ș", "s").replace("ş", "s")
             .replace("ț", "t").replace("ţ", "t")
             .replace("Ă", "A").replace("Â", "A").replace("Î", "I")
             .replace("Ș", "S").replace("Ş", "S")
             .replace("Ț", "T").replace("Ţ", "T"))

PROF_TEMPLATES = [
    "cine preda {N}",
    "cine preda {N}?",
    "cine tine cursul la {N}",
    "cine este profesor la {N}",
    "cine este titularul disciplinei {N}",
    "cine preda materia {N}",
    "profesorul de la {N}",
    "cine sunt profesorii la {N}",
]
CREDITS_TEMPLATES = [
    "cate credite are {N}",
    "cate credite are {N}?",
    "cate credite are materia {N}",
    "creditele pentru {N}",
    "{N} cate credite",
]
HOURS_TEMPLATES = [
    "cate ore are {N}",
    "cate ore pe saptamana are {N}",
    "cate ore am la {N}",
    "{N} cate ore",
]
YEAR_TEMPLATES = [
    "in ce an se face {N}",
    "in ce an se face {N}?",
    "in ce an se preda {N}",
    "anul de studiu pentru {N}",
]
SEMESTER_TEMPLATES = [
    "in ce semestru se face {N}",
    "in ce semestru se face {N}?",
    "in ce semestru se preda {N}",
    "semestrul pentru {N}",
]
EVAL_TEMPLATES = [
    "cum se evalueaza la {N}",
    "ce tip de evaluare are {N}",
    "are examen la {N}",
    "evaluarea la {N}",
]

def fetch_facts(cur, source):
    cur.execute(
        "SELECT answer FROM knowledge_base "
        "WHERE source = %s AND answer ~ %s LIMIT 1",
        (source, r"^Disciplina .+? are \d+ credite\.?$"),
    )
    r = cur.fetchone()
    if not r:
        return None
    ans = r[0]
    m = re.match(r"^Disciplina (.+?) are (\d+) credite\.?$", ans)
    if not m:
        return None
    name = m.group(1).strip()
    facts = {"name": name, "credits": ans}

    cur.execute(
        "SELECT answer FROM knowledge_base WHERE source = %s AND answer ILIKE %s LIMIT 1",
        (source, "Titularii de curs%"),
    )
    r = cur.fetchone()
    facts["prof"] = r[0] if r else None

    cur.execute(
        "SELECT answer FROM knowledge_base WHERE source = %s AND answer ~ %s LIMIT 1",
        (source, r"^Disciplina .+? are \d+ ore pe s[ăa]pt[ăa]m[âa]n[ăa]"),
    )
    r = cur.fetchone()
    facts["hours"] = r[0] if r else None

    cur.execute(
        "SELECT answer FROM knowledge_base WHERE source = %s AND answer ~ %s LIMIT 1",
        (source, r"^Disciplina .+? se studiaz[ăa] [îi]n anul"),
    )
    r = cur.fetchone()
    facts["year"] = r[0] if r else None

    cur.execute(
        "SELECT answer FROM knowledge_base WHERE source = %s AND answer ~ %s LIMIT 1",
        (source, r"^Disciplina .+? se studiaz[ăa] [îi]n semestrul"),
    )
    r = cur.fetchone()
    facts["sem"] = r[0] if r else None

    cur.execute(
        "SELECT answer FROM knowledge_base WHERE source = %s AND answer ILIKE %s LIMIT 1",
        (source, "Tipul de evaluare la disciplina%"),
    )
    r = cur.fetchone()
    facts["eval"] = r[0] if r else None
    return facts

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("DELETE FROM knowledge_base WHERE source = %s", (SOURCE,))
    print(f"Cleared {cur.rowcount} previous {SOURCE} rows.")
    conn.commit()

    cur.execute("SELECT DISTINCT source FROM knowledge_base WHERE source LIKE '%.pdf' ORDER BY source")
    sources = [r[0] for r in cur.fetchall()]
    print(f"Scanning {len(sources)} PDFs.")

    pairs = []
    for src in sources:
        f = fetch_facts(cur, src)
        if not f:
            print(f"  [skip] {src}: no canonical credits row")
            continue
        name = f["name"]
        names = {
            strip_diacritics(name).lower(),
            name,
        }
        for n in names:
            for tpl in PROF_TEMPLATES:
                if f["prof"]:
                    pairs.append((tpl.format(N=n), f["prof"]))
            for tpl in CREDITS_TEMPLATES:
                if f["credits"]:
                    pairs.append((tpl.format(N=n), f["credits"]))
            for tpl in HOURS_TEMPLATES:
                if f["hours"]:
                    pairs.append((tpl.format(N=n), f["hours"]))
            for tpl in YEAR_TEMPLATES:
                if f["year"]:
                    pairs.append((tpl.format(N=n), f["year"]))
            for tpl in SEMESTER_TEMPLATES:
                if f["sem"]:
                    pairs.append((tpl.format(N=n), f["sem"]))
            for tpl in EVAL_TEMPLATES:
                if f["eval"]:
                    pairs.append((tpl.format(N=n), f["eval"]))

    print(f"Generated {len(pairs)} Q&A pairs.")
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
        if inserted % 100 == 0:
            conn.commit()
            print(f"  inserted {inserted}/{len(pairs)}")
    conn.commit()
    cur.close()
    conn.close()
    print(f"Done. Inserted {inserted} rows with source='{SOURCE}'.")

if __name__ == "__main__":
    main()
