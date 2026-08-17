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

    cur.execute("ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS status VARCHAR(16)")
    cur.execute("ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS quality_score DOUBLE PRECISION")
    cur.execute("ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS derived_from_message_id BIGINT")

    cur.execute("UPDATE knowledge_base SET status = 'active' WHERE status IS NULL")
    cur.execute("UPDATE knowledge_base SET quality_score = 0 WHERE quality_score IS NULL")
    print("knowledge_base columns ensured + backfilled.")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id BIGSERIAL PRIMARY KEY,
            message_id BIGINT NOT NULL,
            username VARCHAR(255) NOT NULL,
            rating VARCHAR(16) NOT NULL,
            correction TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_feedback_message_id ON feedback(message_id)")
    print("feedback table ready.")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS message_chunks (
            message_id BIGINT NOT NULL,
            chunk_id BIGINT NOT NULL,
            score DOUBLE PRECISION,
            PRIMARY KEY (message_id, chunk_id)
        )
    """)
    print("message_chunks table ready.")

    conn.commit()

    cur.execute("""
        SELECT status, COUNT(*) FROM knowledge_base
        GROUP BY status ORDER BY status NULLS LAST
    """)
    print("\nknowledge_base by status:")
    for s, n in cur.fetchall():
        print(f"  {s or '<null>'}: {n}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
