import os
import json
import psycopg2
from datetime import datetime
from pathlib import Path

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "chatbot_db",
    "user": "postgres",
    "password": os.getenv("DB_PASSWORD", "")
}

OUT_DIR = Path("..")
JSON_OUT = OUT_DIR / "dataset_export.json"
JSONL_OUT = OUT_DIR / "dataset_finetune.jsonl"

SYSTEM_PROMPT = (
    "Ești un asistent virtual pentru Facultatea de Automatică și Calculatoare "
    "din cadrul Universității Tehnice Cluj-Napoca (UTCN). Răspunzi la întrebări "
    "legate de facultate, cursuri, profesori, regulamente, orare, notare și proceduri."
)

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("""
        SELECT question, answer, source
        FROM knowledge_base
        WHERE (status IS NULL OR status = 'active')
          AND chunk_type = 'qna'
          AND question IS NOT NULL
          AND answer IS NOT NULL
        ORDER BY id
    """)
    rows = cur.fetchall()

    entries = []
    for q, a, src in rows:
        entries.append({
            "input": q.strip(),
            "output": a.strip(),
            "source": src or "unknown"
        })

    with JSON_OUT.open("w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    with JSONL_OUT.open("w", encoding="utf-8") as f:
        for e in entries:
            obj = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": e["input"]},
                    {"role": "assistant", "content": e["output"]}
                ]
            }
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    by_source = {}
    for e in entries:
        by_source[e["source"]] = by_source.get(e["source"], 0) + 1

    print(f"[{datetime.now().isoformat(timespec='seconds')}] Exported {len(entries)} active Q&A pairs.")
    print(f"  -> {JSON_OUT}")
    print(f"  -> {JSONL_OUT}")
    print()
    print("By source:")
    for src, n in sorted(by_source.items()):
        print(f"  {src:<30} {n:>5}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
