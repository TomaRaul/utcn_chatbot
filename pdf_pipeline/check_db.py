import os
import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "chatbot_db",
    "user": "postgres",
    "password": os.getenv("DB_PASSWORD", "")
}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM knowledge_base")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM knowledge_base WHERE embedding IS NOT NULL")
    with_emb = cur.fetchone()[0]

    print(f"Total entries:        {total}")
    print(f"Entries w/ embedding: {with_emb}")
    print(f"Entries w/o embedding: {total - with_emb}")
    print()

    cur.execute("""
        SELECT source, COUNT(*) AS chunks,
               COUNT(embedding) AS with_emb
        FROM knowledge_base
        GROUP BY source
        ORDER BY source
    """)
    rows = cur.fetchall()
    print(f"{'Source':<45} {'Chunks':>8} {'WithEmb':>8}")
    print("-" * 65)
    for source, chunks, with_emb in rows:
        print(f"{(source or '<null>'):<45} {chunks:>8} {with_emb:>8}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
