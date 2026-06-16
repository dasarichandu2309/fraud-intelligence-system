from db import get_connection

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    # USERS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    # HISTORY
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id SERIAL PRIMARY KEY,
        user_id INTEGER,
        amount FLOAT,
        hour INTEGER,
        fraud INTEGER,
        risk INTEGER,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # BLACKLIST
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS blacklist (
        user_id INTEGER PRIMARY KEY,
        reason TEXT,
        flagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # AUDIT LOGS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY,
        username TEXT,
        action TEXT,
        amount FLOAT,
        fraud INTEGER,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    create_tables()