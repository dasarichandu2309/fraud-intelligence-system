from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import get_connection
from jose import jwt, JWTError
from pydantic import BaseModel
import datetime
import hashlib

app = FastAPI()

# ================= CONFIG ================= #
security = HTTPBearer()
SECRET_KEY = "supersecretkey"
ALGORITHM = "HS256"

# ================= PASSWORD ================= #
def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str):
    return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password

# ================= AUTH ================= #
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ================= LOGIN ================= #
class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/login")
def login(data: LoginRequest):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE username=%s", (data.username,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if not user or not verify_password(data.password, user[2]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = jwt.encode({
        "sub": user[1],
        "role": user[3],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=5)
    }, SECRET_KEY, algorithm=ALGORITHM)

    return {"access_token": token}

# ================= PREDICT ================= #
@app.post("/predict")
def predict(data: dict, user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    user_id = data.get("user_id")
    amount = data.get("amount", 0)
    hour = data.get("hour", 0)

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")

    fraud = amount > 10000
    risk = "HIGH" if amount > 20000 else "MEDIUM" if amount > 10000 else "LOW"

    cursor.execute(
        "INSERT INTO history (user_id, amount, hour, fraud, risk) VALUES (%s, %s, %s, %s, %s)",
        (user_id, amount, hour, fraud, risk)
    )

    if fraud:
        cursor.execute(
            "INSERT INTO blacklist (user_id, reason) VALUES (%s, %s)",
            (user_id, "Fraud detected")
        )

    conn.commit()
    cursor.close()
    conn.close()

    return {"fraud": fraud, "risk": risk}

# ================= TRANSACTION ================= #
@app.post("/transaction")
def add_transaction(data: dict, user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    user_id = data.get("user_id")
    amount = data.get("amount", 0)

    fraud = amount > 10000

    cursor.execute(
        "INSERT INTO history (user_id, amount, hour, fraud, risk) VALUES (%s, %s, %s, %s, %s)",
        (user_id, amount, 0, fraud, 0)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "Transaction added", "fraud": fraud}

# ================= HISTORY ================= #
@app.get("/history/{user_id}")
def get_history(user_id: str, user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM history WHERE user_id=%s ORDER BY id DESC",
        (user_id,)
    )
    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return {"history": data}

# ================= BLACKLIST ================= #
@app.post("/blacklist")
def blacklist_user(user_id: str, reason: str, user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO blacklist (user_id, reason) VALUES (%s, %s)",
        (user_id, reason)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "User blacklisted"}

@app.delete("/blacklist/{user_id}")
def remove_blacklist(user_id: str, user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM blacklist WHERE user_id=%s", (user_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "Removed from blacklist"}
@app.get("/stats")
def get_stats(user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    # total transactions
    cursor.execute("SELECT COUNT(*) FROM history")
    total = cursor.fetchone()[0]

    # fraud count
    cursor.execute("SELECT COUNT(*) FROM history WHERE fraud=TRUE")
    fraud = cursor.fetchone()[0]

    safe = total - fraud

    # fraud by user
    cursor.execute("""
        SELECT user_id, COUNT(*) 
        FROM history 
        WHERE fraud=TRUE 
        GROUP BY user_id
    """)
    fraud_users = cursor.fetchall()

    # transactions over time
    cursor.execute("""
        SELECT DATE(time), COUNT(*) 
        FROM history 
        GROUP BY DATE(time)
        ORDER BY DATE(time)
    """)
    trend = cursor.fetchall()

    cursor.close()
    conn.close()

    return {
        "total": total,
        "fraud": fraud,
        "safe": safe,
        "fraud_users": fraud_users,
        "trend": trend
    }

# ================= ROOT ================= #
@app.get("/")
def home():
    return {"message": "Fraud Detection API running 🚀"}