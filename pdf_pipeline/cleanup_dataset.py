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

    cur.execute("SELECT COUNT(*) FROM knowledge_base WHERE source = 'dataset.json'")
    before = cur.fetchone()[0]
    print(f"Entries with source='dataset.json' before cleanup: {before}")

    cur.execute("DELETE FROM knowledge_base WHERE source = 'dataset.json'")
    deleted = cur.rowcount
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM knowledge_base")
    total_after = cur.fetchone()[0]

    print(f"Deleted: {deleted}")
    print(f"Remaining entries (PDF-only KB): {total_after}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
