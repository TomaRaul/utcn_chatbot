import os
import time
import shutil
import requests
import psycopg2
import fitz
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WATCH_FOLDER = "./pdf_input"
PROCESSED_FOLDER = "./pdf_processed"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "chatbot_db",
    "user": "postgres",
    "password": os.getenv("DB_PASSWORD", "")
}

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()

def clean_text(text):
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(lines)

def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    text = clean_text(text)
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            tail = text[start:].strip()
            if tail:
                chunks.append(tail)
            break
        for delim in ["\n\n", ". ", "\n", " "]:
            idx = text.rfind(delim, start, end)
            if idx > start + chunk_size // 2:
                end = idx + len(delim)
                break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
        if start < 0:
            start = 0
    return chunks

def get_embedding(text):
    try:
        response = requests.post(
            OLLAMA_EMBED_URL,
            json={"model": EMBEDDING_MODEL, "prompt": text},
            timeout=60
        )
        response.raise_for_status()
        return response.json()["embedding"]
    except Exception as e:
        log(f"  Embedding error: {e}")
        return None

def format_vector(embedding):
    return "[" + ",".join(map(str, embedding)) + "]"

def ensure_knowledge_base_table(cur):
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

def save_chunks_to_database(chunks, source):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    ensure_knowledge_base_table(cur)

    count = 0
    for i, chunk in enumerate(chunks):
        embedding = get_embedding(chunk)
        if embedding:
            cur.execute(
                "INSERT INTO knowledge_base (question, answer, source, embedding, chunk_type) VALUES (%s, %s, %s, %s, %s)",
                (f"Fragment {i+1}/{len(chunks)} din {source}", chunk, source, format_vector(embedding), "section")
            )
            count += 1
        else:
            log(f"  Skipping chunk {i+1} (no embedding)")

    conn.commit()
    cur.close()
    conn.close()
    return count

def process_pdf(pdf_path):
    filename = os.path.basename(pdf_path)
    log(f"Processing: {filename}")
    try:
        text = extract_text_from_pdf(pdf_path)
        log(f"  Extracted {len(text)} characters")

        chunks = chunk_text(text)
        log(f"  Split into {len(chunks)} chunks")

        if not chunks:
            log(f"  WARNING: No chunks generated for {filename}")
            return

        count = save_chunks_to_database(chunks, filename)
        log(f"  Saved {count}/{len(chunks)} chunks with embeddings")

        dest = Path(PROCESSED_FOLDER) / filename
        if dest.exists():
            dest.unlink()
        shutil.move(pdf_path, str(dest))

        log(f"  Done! PDF moved to pdf_processed/")
    except Exception as e:
        log(f"  ERROR: {e}")

class PDFHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.lower().endswith(".pdf"):
            time.sleep(1)
            process_pdf(event.src_path)

def main():
    Path(WATCH_FOLDER).mkdir(parents=True, exist_ok=True)
    Path(PROCESSED_FOLDER).mkdir(parents=True, exist_ok=True)

    existing = list(Path(WATCH_FOLDER).glob("*.pdf"))
    if existing:
        log(f"Found {len(existing)} existing PDF(s) to process first.")
        for pdf in existing:
            process_pdf(str(pdf))

    log(f"Monitoring '{WATCH_FOLDER}' for new PDFs... Press Ctrl+C to stop.")
    observer = Observer()
    observer.schedule(PDFHandler(), WATCH_FOLDER, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
