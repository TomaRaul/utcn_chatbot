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

def find_fact(blob, regex, group=1):
    m = re.search(regex, blob, re.IGNORECASE | re.DOTALL)
    return m.group(group).strip() if m else None

CREDITS_TEMPLATES = [
    "cate credite are {N}",
    "cate credite are {N}?",
    "cate credite are materia {N}",
    "cate credite are disciplina {N}",
    "cate credite valoreaza {N}",
    "cu cate credite e {N}",
    "creditele pentru {N}",
    "numarul de credite la {N}",
    "valoarea creditelor pentru {N}",
    "cate credite primesc la {N}",
    "{N} cate credite",
    "credite {N}",
]

HOURS_TEMPLATES = [
    "cate ore are {N}",
    "cate ore pe saptamana are {N}",
    "cate ore are {N} pe saptamana",
    "cate ore am la {N}",
    "numarul de ore la {N}",
    "orele de {N}",
    "{N} cate ore",
    "cat dureaza {N}",
    "cate ore se fac la {N}",
]

YEAR_TEMPLATES = [
    "in ce an se face {N}",
    "in ce an se face {N}?",
    "in ce an se preda {N}",
    "{N} in ce an",
    "anul de studiu pentru {N}",
    "in ce an se studiaza {N}",
    "cand se face {N}",
    "din ce an e {N}",
    "in ce an de studiu este {N}",
    "anul materiei {N}",
]

SEMESTER_TEMPLATES = [
    "in ce semestru se face {N}",
    "in ce semestru se face {N}?",
    "in ce semestru se preda {N}",
    "{N} in ce semestru",
    "semestrul pentru {N}",
    "in ce semestru se studiaza {N}",
    "cand se face {N} semestru",
    "din ce semestru este {N}",
    "semestrul materiei {N}",
]

EVAL_TEMPLATES = [
    "cum se evalueaza la {N}",
    "ce tip de evaluare are {N}",
    "are examen la {N}",
    "ce examen e la {N}",
    "cum se da {N}",
    "ce tip de examen e la {N}",
    "evaluarea la {N}",
    "{N} examen sau colocviu",
    "tipul examenului la {N}",
    "ce e la {N} examen sau colocviu",
]

def collect_facts(cur):
    cur.execute("SELECT DISTINCT source FROM knowledge_base WHERE source LIKE '%.pdf'")
    sources = [r[0] for r in cur.fetchall()]
    out = {}
    for src in sources:
        cur.execute("SELECT question, answer FROM knowledge_base WHERE source = %s", (src,))
        rows = cur.fetchall()
        blob = "\n".join((q or "") + "\n" + (a or "") for q, a in rows)

        name = find_fact(blob, r"Disciplina\s+(.+?)\s+are\s+\d+\s+credite")
        if not name:
            continue
        name = name.rstrip(".")

        credits_a = find_fact(blob, r"(Disciplina\s+.+?\s+are\s+\d+\s+credite\.?)", group=1)
        hours_a   = find_fact(blob, r"(Disciplina\s+.+?\s+are\s+\d+\s+ore\s+pe\s+s[ăa]pt[ăa]m[âa]n[ăa][^.]*\.?)", group=1)
        year_a    = find_fact(blob, r"(Disciplina\s+.+?\s+se\s+studiaz[ăa]\s+(?:se\s+)?[îi]n\s+anul\s+[IViv\d]+\.?)", group=1)
        sem_a     = find_fact(blob, r"(Disciplina\s+.+?\s+se\s+studiaz[ăa]\s+(?:se\s+)?[îi]n\s+semestrul\s+\d+\.?)", group=1)
        eval_a    = find_fact(blob, r"(Tipul\s+de\s+evaluare\s+la\s+disciplina\s+.+?\s+este\s+\w+(?:\s+\([^)]+\))?\.?)", group=1)

        out[src] = {
            "name": name,
            "credits": credits_a,
            "hours":   hours_a,
            "year":    year_a,
            "sem":     sem_a,
            "eval":    eval_a,
        }
    return out

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("DELETE FROM knowledge_base WHERE source = %s", (SOURCE,))
    print(f"Cleared {cur.rowcount} previous {SOURCE} rows.")
    conn.commit()

    facts = collect_facts(cur)
    print(f"Found facts for {len(facts)} disciplines.")

    pairs = []
    for src, f in facts.items():
        names = {f["name"], strip_diacritics(f["name"])}
        for n in names:
            if f["credits"]:
                for tpl in CREDITS_TEMPLATES:
                    pairs.append((tpl.format(N=n), f["credits"]))
            if f["hours"]:
                for tpl in HOURS_TEMPLATES:
                    pairs.append((tpl.format(N=n), f["hours"]))
            if f["year"]:
                for tpl in YEAR_TEMPLATES:
                    pairs.append((tpl.format(N=n), f["year"]))
            if f["sem"]:
                for tpl in SEMESTER_TEMPLATES:
                    pairs.append((tpl.format(N=n), f["sem"]))
            if f["eval"]:
                for tpl in EVAL_TEMPLATES:
                    pairs.append((tpl.format(N=n), f["eval"]))

    print(f"Generated {len(pairs)} fact-phrasing Q&A pairs.")
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
