import os
import psycopg2
import sys

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "chatbot_db",
    "user": "postgres",
    "password": os.getenv("DB_PASSWORD", "")
}

def main():
    source = sys.argv[1] if len(sys.argv) > 1 else "programareaCalculatoarelor.pdf"
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "SELECT question, answer FROM knowledge_base WHERE source = %s ORDER BY id",
        (source,)
    )
    for q, a in cur.fetchall():
        print("=" * 80)
        print(q)
        print("-" * 80)
        print(a[:600])
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
