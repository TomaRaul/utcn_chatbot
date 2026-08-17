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
SOURCE = "spec_directq"

INT_TO_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}
SPEC_LABELS = {
    "CTI": "Calculatoare și Tehnologia Informației",
    "Calculatoare": "Calculatoare",
    "TI": "Tehnologia Informației",
}

def get_embedding(text):
    r = requests.post(OLLAMA_URL, json={"model": EMBEDDING_MODEL, "prompt": text}, timeout=120)
    r.raise_for_status()
    return r.json()["embedding"]

def fmt_vec(emb):
    return "[" + ",".join(map(str, emb)) + "]"

def aggregate(cur):
    cur.execute("SELECT DISTINCT source FROM knowledge_base WHERE source LIKE '%.pdf'")
    sources = [r[0] for r in cur.fetchall()]
    out = defaultdict(list)
    for src in sources:
        cur.execute("SELECT question, answer FROM knowledge_base WHERE source = %s", (src,))
        blob = "\n".join((q or "") + "\n" + (a or "") for q, a in cur.fetchall())
        m = re.search(r"Disciplina\s+(.+?)\s+are\s+(\d+)\s+credite", blob, re.IGNORECASE)
        if not m:
            continue
        name = m.group(1).strip().rstrip(".")
        credits = int(m.group(2))
        m = re.search(r"studiaz[ăa]\s+(?:se\s+)?[îi]n\s+anul\s+([IViv]+|\d+)", blob, re.IGNORECASE)
        if not m: continue
        tok = m.group(1).lower()
        year = int(tok) if tok.isdigit() else {"i":1,"ii":2,"iii":3,"iv":4}.get(tok)
        if year is None: continue
        spec = None
        m = re.search(r"Specializarea:\s*(CTI|Calculatoare|TI)\b", blob)
        if m: spec = m.group(1)
        if year < 4 and spec != "TI":
            spec = "CTI"
        out[(year, spec)].append((name, credits))
    return out

QUESTION_TEMPLATES = [
    "spune mi materiile din specializarea de {S_LOWER} din anul {Y}",
    "spune-mi materiile din specializarea de {S_LOWER} din anul {Y}",
    "spune mi materiile din specializarea {S_LOWER} din anul {Y}",
    "spune mi materiile de la specializarea {S_LOWER} anul {Y}",
    "care sunt materiile din specializarea de {S_LOWER} din anul {Y}",
    "care sunt materiile de la specializarea {S_LOWER} anul {Y}",
    "ce materii sunt la specializarea {S_LOWER} in anul {Y}",
    "ce materii are specializarea {S_LOWER} din anul {Y}",
    "materiile specializarii {S_LOWER} anul {Y}",
    "materiile din pachetul {S_LOWER} din anul {Y}",
    "spune materiile din pachetul {S_LOWER} anul {Y}",
    "ce materii sunt in pachetul {S_LOWER} din anul {Y}",
    "ce intra in pachetul {S_LOWER} din anul {Y}",
    "ce face pachetul {S_LOWER} din anul {Y}",
    "ce face specializarea {S_LOWER} in anul {Y}",
]

def build_answer(spec_key, year_arabic, names):
    label = SPEC_LABELS.get(spec_key, spec_key)
    listing = ", ".join(names)
    bullets = "\n".join(f"- {n}" for n in names)
    if spec_key == "Calculatoare":
        return (
            f"Specializarea Calculatoare din anul {year_arabic} "
            f"(specializarea de calculatoare, pachetul Calculatoare). "
            f"Materiile din specializarea Calculatoare anul {year_arabic}:\n{bullets}"
        )
    if spec_key == "TI":
        return (
            f"Specializarea Tehnologia Informației (TI) din anul {year_arabic} "
            f"(specializarea de tehnologia informației, pachetul TI). "
            f"Materiile din specializarea TI anul {year_arabic}:\n{bullets}"
        )
    return (
        f"Anul {year_arabic} ({label}). Materiile anului {year_arabic}:\n{bullets}"
    )

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("DELETE FROM knowledge_base WHERE source = %s", (SOURCE,))
    print(f"Cleared {cur.rowcount} previous {SOURCE} rows.")
    conn.commit()

    grouped = aggregate(cur)

    common_y4 = grouped.get((4, "CTI"), [])
    if common_y4:
        for sp in ("Calculatoare", "TI"):
            if (4, sp) in grouped:
                grouped[(4, sp)].extend(common_y4)
            else:
                grouped[(4, sp)] = list(common_y4)

    pairs = []

    for (year, spec), subs in grouped.items():
        if spec == "CTI" or spec is None:
            continue
        names = sorted({n for n, _ in subs}, key=lambda s: s.lower())
        year_arabic = str(year)
        year_roman = INT_TO_ROMAN.get(year, str(year))

        if spec == "Calculatoare":
            spec_words = ["calculatoare", "Calculatoare"]
        else:
            spec_words = ["tehnologia informatiei", "tehnologia informației",
                          "TI", "ti", "Tehnologia Informației"]

        answer = build_answer(spec, year_arabic, names)
        for s_word in spec_words:
            for tpl in QUESTION_TEMPLATES:
                q = tpl.format(S_LOWER=s_word, Y=year_arabic)
                pairs.append((q, answer))
                pairs.append((tpl.format(S_LOWER=s_word, Y=year_roman), answer))

    print(f"Generated {len(pairs)} direct Q&A pairs.")
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
    cur.close()
    conn.close()
    print(f"Done. Inserted {inserted} rows with source='{SOURCE}'.")

if __name__ == "__main__":
    main()
