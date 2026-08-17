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
    "host": "localhost",
    "port": 5432,
    "database": "chatbot_db",
    "user": "postgres",
    "password": os.getenv("DB_PASSWORD", ""),
}

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"
SOURCE = "manifest_phrasings"

ROMAN_TO_INT = {"I": 1, "II": 2, "III": 3, "IV": 4}
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
        cur.execute(
            "SELECT question, answer FROM knowledge_base WHERE source = %s",
            (src,),
        )
        rows = cur.fetchall()
        blob = "\n".join((q or "") + "\n" + (a or "") for q, a in rows)

        name, credits, year, spec = None, None, None, None
        m = re.search(r"Disciplina\s+(.+?)\s+are\s+(\d+)\s+credite", blob, re.IGNORECASE)
        if m:
            name = m.group(1).strip().rstrip(".")
            credits = int(m.group(2))
        m = re.search(r"studiaz[ăa]\s+(?:se\s+)?[îi]n\s+anul\s+([IViv]+|\d+)", blob, re.IGNORECASE)
        if m:
            tok = m.group(1).lower()
            year = int(tok) if tok.isdigit() else {"i": 1, "ii": 2, "iii": 3, "iv": 4}.get(tok)
        m = re.search(r"Specializarea:\s*(CTI|Calculatoare|TI)\b", blob)
        if m:
            spec = m.group(1)

        if not name or credits is None or year is None:
            continue
        if year < 4 and spec != "TI":
            spec = "CTI"
        out[(year, spec)].append((name, credits))
    return out

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("DELETE FROM knowledge_base WHERE source = %s", (SOURCE,))
    print(f"Cleared {cur.rowcount} previous {SOURCE} rows.")
    conn.commit()

    grouped = aggregate(cur)
    print(f"Aggregated {len(grouped)} (year, spec) buckets.")

    common_y4 = grouped.get((4, "CTI"), [])
    if common_y4:
        for sp in ("Calculatoare", "TI"):
            if (4, sp) in grouped:
                grouped[(4, sp)].extend(common_y4)
            else:
                grouped[(4, sp)] = list(common_y4)

    pairs = []
    for (year, spec), subs in grouped.items():
        names = sorted({n for n, _ in subs}, key=lambda s: s.lower())
        if not names:
            continue
        year_roman = INT_TO_ROMAN.get(year, str(year))
        year_arabic = str(year)
        spec_label = SPEC_LABELS.get(spec, spec)
        listing = ", ".join(names)
        bullets = "\n".join(f"- {n}" for n in names)

        is_year4_split = (year == 4 and spec != "CTI")

        if is_year4_split:
            for yr in (year_roman, year_arabic):
                spec_forms = [
                    f"specializarea {spec}",
                    f"specializarea {spec_label}",
                    f"pachetul {spec}",
                    f"pachetul de {spec}",
                    f"pachetul de {spec_label}",
                    f"sectia {spec}",
                ]
                for sf in spec_forms:
                    answer = (
                        f"Materiile din {sf} din anul {yr} sunt: {listing}."
                    )
                    bullets_answer = (
                        f"Materiile din {sf} din anul {yr}:\n{bullets}"
                    )
                    questions = [
                        f"Spune-mi materiile din {sf} din anul {yr}",
                        f"Spune mi materiile din {sf} din anul {yr}",
                        f"Care sunt materiile din {sf} din anul {yr}?",
                        f"Care sunt materiile anului {yr} din {sf}?",
                        f"Care sunt materiile din anul {yr} din {sf}?",
                        f"Materiile din {sf} din anul {yr}",
                        f"Materiile anului {yr} {sf}",
                        f"Lista materiilor din {sf} anul {yr}",
                        f"Enumera materiile din {sf} din anul {yr}",
                        f"Ce materii are {sf} din anul {yr}?",
                        f"Ce materii intra in {sf} din anul {yr}?",
                        f"Ce intra in {sf} din anul {yr}?",
                    ]
                    for q in questions:
                        pairs.append((q, answer))
                    pairs.append((f"Lista materii {sf} anul {yr}", bullets_answer))
        else:
            for yr in (year_roman, year_arabic):
                answer = f"Materiile din anul {yr} sunt: {listing}."
                bullets_answer = f"Materiile din anul {yr}:\n{bullets}"
                for q in [
                    f"Spune-mi materiile din anul {yr}",
                    f"Spune mi materiile din anul {yr}",
                    f"Care sunt materiile din anul {yr}?",
                    f"Care sunt materiile anului {yr}?",
                    f"Materiile din anul {yr}",
                    f"Materiile anului {yr}",
                    f"Lista materiilor din anul {yr}",
                    f"Enumera materiile din anul {yr}",
                ]:
                    pairs.append((q, answer))
                pairs.append((f"Lista materii anul {yr}", bullets_answer))

    print(f"Generated {len(pairs)} phrasing Q&A pairs.")

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
