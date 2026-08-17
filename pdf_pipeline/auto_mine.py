import os
import json
import re
import sys
import requests
import psycopg2
from datetime import datetime

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "chatbot_db",
    "user": "postgres",
    "password": os.getenv("DB_PASSWORD", "")
}

OLLAMA_BASE = "http://localhost:11434"
GEN_MODEL = "llama3.2"
EMBED_MODEL = "nomic-embed-text"

VARIATIONS_PER_QNA = 3
SKIP_VARIATIONS = "--no-variations" in sys.argv

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def get_embedding(text):
    r = requests.post(f"{OLLAMA_BASE}/api/embeddings",
                      json={"model": EMBED_MODEL, "prompt": text},
                      timeout=60)
    r.raise_for_status()
    return r.json()["embedding"]

def format_vector(emb):
    return "[" + ",".join(map(str, emb)) + "]"

def generate_variations(question, n=VARIATIONS_PER_QNA):
    prompt = (
        f"Reformulează următoarea întrebare în {n} variații diferite ca formulare, "
        "dar cu același sens. Răspunde cu o listă numerotată de la 1, "
        "doar întrebările, fără explicații.\n\n"
        f"Întrebare originală: {question}\n\n"
        "Variații:"
    )
    try:
        r = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json={
                "model": GEN_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 256}
            },
            timeout=120
        )
        r.raise_for_status()
        text = r.json().get("response", "")
    except Exception as e:
        log(f"  variation generation failed: {e}")
        return []

    out = []
    for line in text.splitlines():
        line = line.strip()
        line = re.sub(r"^[\d]+[.)\s]+", "", line)
        line = line.strip(' "\'')
        if line and "?" in line and line.lower() != question.lower():
            out.append(line)
    seen = set()
    deduped = []
    for v in out:
        key = re.sub(r"\W+", "", v.lower())
        if key not in seen:
            seen.add(key)
            deduped.append(v)
    return deduped[:n]

def fetch_thumbs_up_messages(cur):
    cur.execute("""
        SELECT m.id, m.content, m.conversation_id
        FROM messages m
        WHERE m.role = 'assistant'
          AND EXISTS (
              SELECT 1 FROM feedback f
              WHERE f.message_id = m.id AND f.rating = 'up'
          )
          AND NOT EXISTS (
              SELECT 1 FROM feedback f
              WHERE f.message_id = m.id AND f.rating = 'down'
          )
          AND NOT EXISTS (
              SELECT 1 FROM knowledge_base kb
              WHERE kb.derived_from_message_id = m.id
          )
        ORDER BY m.id
    """)
    return cur.fetchall()

def get_preceding_user_question(cur, assistant_message_id, conversation_id):
    cur.execute("""
        SELECT content FROM messages
        WHERE conversation_id = %s AND role = 'user' AND id < %s
        ORDER BY id DESC LIMIT 1
    """, (conversation_id, assistant_message_id))
    row = cur.fetchone()
    return row[0] if row else None

def insert_pending(cur, question, answer, derived_from_message_id, source="auto-mined"):
    try:
        emb = get_embedding(f"{question} {answer}")
    except Exception as e:
        log(f"  embedding failed: {e}")
        return False
    cur.execute("""
        INSERT INTO knowledge_base
            (question, answer, source, embedding, chunk_type, status, quality_score, derived_from_message_id)
        VALUES (%s, %s, %s, %s, 'qna', 'pending', 0, %s)
    """, (question, answer, source, format_vector(emb), derived_from_message_id))
    return True

def main():
    log("Auto-mine starting.")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    rows = fetch_thumbs_up_messages(cur)
    log(f"Found {len(rows)} upvoted messages without prior mining.")

    mined = 0
    variations_added = 0
    for asst_id, answer, conv_id in rows:
        question = get_preceding_user_question(cur, asst_id, conv_id)
        if not question or not answer or not answer.strip():
            continue
        if "Nu am informații" in answer:
            continue

        log(f"  message {asst_id}: '{question[:60]}...' -> '{answer[:60]}...'")
        if insert_pending(cur, question, answer, asst_id):
            mined += 1

            if not SKIP_VARIATIONS:
                variations = generate_variations(question)
                for v in variations:
                    if insert_pending(cur, v, answer, asst_id, source="auto-mined-variation"):
                        variations_added += 1
                if variations:
                    log(f"    + {len(variations)} variations")

            conn.commit()

    log(f"Done. Mined {mined} originals + {variations_added} variations into 'pending' queue.")
    log("Run admin panel to review and approve.")
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
