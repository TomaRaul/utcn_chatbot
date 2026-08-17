import os
import sys

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
SOURCE = "cazare_dates"

def get_embedding(text):
    r = requests.post(OLLAMA_URL, json={"model": EMBEDDING_MODEL, "prompt": text}, timeout=120)
    r.raise_for_status()
    return r.json()["embedding"]

def fmt_vec(emb):
    return "[" + ",".join(map(str, emb)) + "]"

FACTS = [
    {
        "answer": "Prima zi de cazare la UTCN este 23.09.2025, intre orele 08:00 si 18:00. In prima zi se cazeaza studentii de anul I licenta.",
        "questions": [
            "care este data primei zile de cazare",
            "care e data primei zile de cazare",
            "care e data pentru prima zi de cazare",
            "care e data pentru prima zi de cazari",
            "in ce data e prima zi de cazare",
            "pe ce data e prima zi de cazare",
            "cand are loc prima zi de cazare",
            "cand e prima zi de cazare",
            "cand este prima zi de cazare",
            "cand incepe cazarea",
            "cand incep cazarile",
            "cand sunt cazarile la UTCN",
            "pe ce data incepe cazarea",
            "in ce zi incepe cazarea",
            "data primei zile de cazare",
            "data inceperii cazarii",
        ],
    },
    {
        "answer": "A doua zi de cazare la UTCN este 24.09.2025, intre orele 08:00 si 20:00. In a doua zi se cazeaza studentii la master, casatoriti, doctoranzi, angajati tineri, anul VI si anul V Arhitectura, studentii anul IV, III si II licenta.",
        "questions": [
            "care e data celei de-a doua zile de cazare",
            "cand are loc a doua zi de cazare",
            "cand e a doua zi de cazare",
            "in ce data este a doua zi de cazare",
            "pe ce data e a doua zi de cazare",
            "cand se cazeaza studentii de la master",
            "cand se cazeaza masteranzii",
            "cand se cazeaza doctoranzii",
            "cand se cazeaza studentii din anul II",
            "cand se cazeaza studentii din anul III",
            "cand se cazeaza studentii din anul IV",
        ],
    },
    {
        "answer": "A treia zi de cazare la UTCN este 25.09.2025. Intre orele 08:00 si 11:00 se prezinta studentii care nu au putut veni in zilele anterioare si au anuntat comisia de cazare. Intre orele 13:00 si 18:00 sunt cazati studentii care primesc drept de cazare prin glisarea listelor, in limita locurilor disponibile.",
        "questions": [
            "care e data celei de-a treia zile de cazare",
            "cand are loc a treia zi de cazare",
            "cand e a treia zi de cazare",
            "in ce data este a treia zi de cazare",
            "pe ce data e a treia zi de cazare",
            "ce se intampla pe 25 septembrie cu cazarea",
        ],
    },
    {
        "answer": "A patra zi de cazare la UTCN este 26.09.2025, intre orele 09:00 si 14:00. In aceasta zi se cazeaza studentii cu drept de cazare in urma unei noi glisari a listelor, in limita locurilor ramase din ziua anterioara.",
        "questions": [
            "care e data celei de-a patra zile de cazare",
            "cand are loc a patra zi de cazare",
            "cand e a patra zi de cazare",
            "in ce data este a patra zi de cazare",
            "cand se termina cazarile la UTCN",
            "cand e ultima zi de cazare",
        ],
    },
    {
        "answer": "Cazarea studentilor in caminele UTCN pentru anul universitar 2025-2026 se desfasoara in perioada 23-26 septembrie 2025.",
        "questions": [
            "in ce perioada e cazarea la UTCN",
            "in ce perioada se face cazarea",
            "care e perioada de cazare la UTCN",
            "intre ce date e cazarea",
            "intre ce date au loc cazarile",
            "cand este perioada de cazare la UTCN",
        ],
    },
    {
        "answer": "Studentii de anul I licenta se cazeaza in prima zi de cazare, pe 23.09.2025, intre orele 08:00 si 18:00.",
        "questions": [
            "cand se cazeaza studentii de anul I",
            "cand se cazeaza bobocii",
            "cand se cazeaza anul 1",
            "cand se cazeaza studentii din anul 1",
            "pe ce data se cazeaza studentii de anul I",
            "in ce zi se cazeaza anul 1",
        ],
    },
]

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("DELETE FROM knowledge_base WHERE source = %s", (SOURCE,))
    print(f"Sters {cur.rowcount} randuri vechi cu source='{SOURCE}'.")
    conn.commit()

    pairs = []
    for fact in FACTS:
        for q in fact["questions"]:
            pairs.append((q, fact["answer"]))

    print(f"Generate {len(pairs)} perechi Q&A.")

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
    conn.commit()
    cur.close()
    conn.close()
    print(f"Gata. Inserate {inserted} randuri cu source='{SOURCE}'.")

if __name__ == "__main__":
    main()
