import psycopg2
from passlib.context import CryptContext
from db import get_connection

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password):
    return pwd_context.hash(password[:72])


def create_user(username, password, role):
    conn = get_connection()
    cursor = conn.cursor()

    hashed_password = hash_password(password)

    try:
        cursor.execute("""
        INSERT INTO users (username, password, role)
        VALUES (%s, %s, %s)
        """, (username, hashed_password, role))

        conn.commit()
        print(f"✅ User '{username}' created as {role}")

    except Exception as e:
        print("❌ Error:", e)

    finally:
        conn.close()


# =========================
# CREATE USERS
# =========================
if __name__ == "__main__":

    # 👑 Admin
    create_user("admin", "admin123", "admin")

    # 🧑‍💻 Analyst
    create_user("analyst", "analyst123", "analyst")