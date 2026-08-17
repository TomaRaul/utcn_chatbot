import sys
import re
import os
from pathlib import Path

import requests
import psycopg2
import fitz

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
PDF_DIR = "./pdf_processed"

def get_embedding(text):
    r = requests.post(OLLAMA_URL, json={"model": EMBEDDING_MODEL, "prompt": text}, timeout=120)
    r.raise_for_status()
    return r.json()["embedding"]

def format_vector(emb):
    return "[" + ",".join(map(str, emb)) + "]"

def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

def extract_facts(text):
    name = None
    m = re.search(r"Denumirea\s+disciplinei\s*[:\n\s]*([^\n]+)", text, re.IGNORECASE)
    if m:
        name = m.group(1).strip()

    year = None
    m = re.search(
        r"Anul\s+de\s+studiu\s*[:\n\s]*([IViv]{1,3}|[1-4])\b",
        text,
        re.IGNORECASE,
    )
    if m:
        year = m.group(1).strip()

    credits = None
    m = re.search(r"Num[ăa]rul\s+de\s+credite\s*[:\n\s]*(\d+)\b", text, re.IGNORECASE)
    if m:
        credits = m.group(1).strip()

    return name, year, credits

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    pdfs = sorted(Path(PDF_DIR).glob("*.pdf"))
    print(f"Scanning {len(pdfs)} PDFs.")

    year_patched = 0
    credit_patched = 0
    extract_fail = 0
    all_ok = 0

    def insert_qna(filename, q, a):
        emb = get_embedding(q + " " + a)
        cur.execute(
            "INSERT INTO knowledge_base (question, answer, source, embedding, chunk_type) "
            "VALUES (%s, %s, %s, %s, %s)",
            (q, a, filename, format_vector(emb), "qna"),
        )

    for pdf in pdfs:
        filename = pdf.name
        text = extract_text(str(pdf))
        name, year, credits = extract_facts(text)

        if not name:
            print(f"  [extract fail] {filename}: no discipline name")
            extract_fail += 1
            continue

        any_change = False

        if year:
            cur.execute(
                "SELECT 1 FROM knowledge_base WHERE source = %s AND answer LIKE %s LIMIT 1",
                (filename, f"%se studiază în anul {year}%"),
            )
            if not cur.fetchone():
                a = f"Disciplina {name} se studiază în anul {year}."
                for q in [
                    f"În ce an se face {name}?",
                    f"În ce an de studiu se predă {name}?",
                    f"Anul de studiu pentru {name}",
                ]:
                    try:
                        insert_qna(filename, q, a)
                    except Exception as e:
                        print(f"  [embed fail year] {filename}: {e}")
                year_patched += 1
                any_change = True

        if credits:
            cur.execute(
                "SELECT 1 FROM knowledge_base WHERE source = %s AND answer LIKE %s LIMIT 1",
                (filename, f"Disciplina {name} are {credits} credite%"),
            )
            if not cur.fetchone():
                a = f"Disciplina {name} are {credits} credite."
                for q in [
                    f"Câte credite are {name}?",
                    f"Cate credite are {name}?",
                    f"Numărul de credite pentru {name}",
                ]:
                    try:
                        insert_qna(filename, q, a)
                    except Exception as e:
                        print(f"  [embed fail credits] {filename}: {e}")
                credit_patched += 1
                any_change = True

        if any_change:
            conn.commit()
            print(f"  [patched] {filename}: {name} -> an {year or '?'}, {credits or '?'} cr")
        else:
            all_ok += 1

    cur.close()
    conn.close()
    print()
    print(f"Year patched: {year_patched} | Credits patched: {credit_patched} | "
          f"already ok: {all_ok} | extract fail: {extract_fail}")

if __name__ == "__main__":
    main()
