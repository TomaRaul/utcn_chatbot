import os
import json
import requests
import psycopg2
from pathlib import Path

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "chatbot_db",
    "user": "postgres",
    "password": os.getenv("DB_PASSWORD", "")
}

DATASET_PATH = "../dataset.json"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"

def get_embedding(text):
    response = requests.post(OLLAMA_URL, json={"model": EMBEDDING_MODEL, "prompt": text}, timeout=60)
    response.raise_for_status()
    return response.json()["embedding"]

def format_vector(embedding):
    return "[" + ",".join(map(str, embedding)) + "]"

def main():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        entries = json.load(f)

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id SERIAL PRIMARY KEY,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            source VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW(),
            embedding TEXT
        )
    """)
    cur.execute("ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS embedding TEXT")

    cur.execute("DELETE FROM knowledge_base WHERE source = 'dataset.json'")
    print("Cleared previous dataset.json entries (PDF fragments preserved).")
    conn.commit()

    count = 0
    total = len(entries)
    for i, entry in enumerate(entries):
        output = entry["output"] if isinstance(entry["output"], str) else " ".join(entry["output"])
        text = entry["input"] + " " + output
        try:
            embedding = get_embedding(text)
            vector_str = format_vector(embedding)
            cur.execute(
                "INSERT INTO knowledge_base (question, answer, source, embedding, chunk_type) VALUES (%s, %s, %s, %s, %s)",
                (entry["input"], output, "dataset.json", vector_str, "qna")
            )
        except Exception as e:
            print(f"  Warning: embedding failed for entry {i+1}, inserting without embedding. Error: {e}")
            cur.execute(
                "INSERT INTO knowledge_base (question, answer, source, chunk_type) VALUES (%s, %s, %s, %s)",
                (entry["input"], output, "dataset.json", "qna")
            )
        count += 1
        if count % 10 == 0:
            conn.commit()
            print(f"  Progress: {count}/{total}")

    conn.commit()
    cur.close()
    conn.close()
    print(f"Imported {count} entries into knowledge_base.")

if __name__ == "__main__":
    main()
