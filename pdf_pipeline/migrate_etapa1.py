import os
import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "chatbot_db",
    "user": "postgres",
    "password": os.getenv("DB_PASSWORD", "")
}

DUPLICATE_SOURCE = "analiza_calc_diferential.pdf"

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS chunk_type VARCHAR(16)")
    print("Ensured chunk_type column exists.")

    cur.execute("""
        UPDATE knowledge_base
        SET chunk_type = 'section'
        WHERE chunk_type IS NULL
          AND question LIKE 'Informații despre%'
    """)
    sections = cur.rowcount

    cur.execute("""
        UPDATE knowledge_base
        SET chunk_type = 'section'
        WHERE chunk_type IS NULL
          AND question LIKE 'Fragment %'
    """)
    fixed_chunks = cur.rowcount

    cur.execute("""
        UPDATE knowledge_base
        SET chunk_type = 'qna'
        WHERE chunk_type IS NULL
    """)
    qna = cur.rowcount

    print(f"Backfilled chunk_type: section={sections + fixed_chunks}, qna={qna}")

    cur.execute("DELETE FROM knowledge_base WHERE source = %s", (DUPLICATE_SOURCE,))
    deleted = cur.rowcount
    print(f"Deleted {deleted} rows from duplicate source '{DUPLICATE_SOURCE}'.")

    conn.commit()

    cur.execute("""
        SELECT chunk_type, COUNT(*)
        FROM knowledge_base
        GROUP BY chunk_type
        ORDER BY chunk_type NULLS LAST
    """)
    print("\nFinal distribution:")
    for ctype, n in cur.fetchall():
        print(f"  {ctype or '<null>'}: {n}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
