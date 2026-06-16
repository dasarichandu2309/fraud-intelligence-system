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

# ================= PASSWORD (FINAL FIX) ================= #

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

# ================= CREATE USER ================= #

@app.post("/create_user")
def create_user(username: str, password: str, role: str = "analyst"):
    conn = get_connection()
    cursor = conn.cursor()

    hashed = hash_password(password)

    try:
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
            (username, hashed, role)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    cursor.close()
    conn.close()

    return {"message": "User created successfully"}

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

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(data.password, user[2]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    payload = {
        "sub": user[1],
        "role": user[3],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=5)
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {"access_token": token}

# ================= PREDICT ================= #

@app.post("/predict")
def predict(data: dict, user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    amount = data.get("amount", 0)

    fraud = amount > 10000
    risk = "HIGH" if amount > 20000 else "MEDIUM" if amount > 10000 else "LOW"

    alert = "⚠️ Suspicious transaction detected!" if fraud else None

    cursor.execute(
        "INSERT INTO transactions (user_id, amount, fraud) VALUES (%s, %s, %s)",
        (user["sub"], amount, fraud)
    )

    if fraud:
        cursor.execute(
            "INSERT INTO blacklist (user_id, reason) VALUES (%s, %s)",
            (user["sub"], "Fraud detected")
        )

    conn.commit()
    cursor.close()
    conn.close()

    return {
        "fraud": fraud,
        "risk": risk,
        "alert": alert
    }

# ================= TRANSACTION ================= #

@app.post("/transaction")
def add_transaction(amount: float, user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    fraud = amount > 10000

    cursor.execute(
        "INSERT INTO transactions (user_id, amount, fraud) VALUES (%s, %s, %s)",
        (user["sub"], amount, fraud)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "Transaction added", "fraud": fraud}

# ================= HISTORY ================= #

@app.get("/history")
def get_history(user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM transactions WHERE user_id=%s ORDER BY id DESC",
        (user["sub"],)
    )
    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return {"history": data}

# ================= AUDIT LOGS ================= #

@app.get("/audit_logs")
def audit_logs(user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM audit_logs ORDER BY time DESC")
    logs = cursor.fetchall()

    cursor.close()
    conn.close()

    return {"logs": logs}

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

@app.get("/blacklist")
def get_blacklist(user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM blacklist")
    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return {"blacklist": data}

@app.delete("/blacklist/{user_id}")
def remove_blacklist(user_id: str, user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM blacklist WHERE user_id=%s",
        (user_id,)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "Removed from blacklist"}

# ================= STATS ================= #

@app.get("/stats")
def get_stats(user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT fraud FROM transactions")
    data = cursor.fetchall()

    total = len(data)
    fraud_count = sum(1 for d in data if d[0])
    safe = total - fraud_count

    cursor.close()
    conn.close()

    return {
        "total": total,
        "fraud": fraud_count,
        "safe": safe
    }

# ================= KPI ================= #

@app.get("/kpi")
def kpi():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM transactions")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM transactions WHERE fraud=TRUE")
    fraud = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return {
        "fraud_rate": round((fraud / total) * 100, 2) if total else 0
    }

# ================= ROOT ================= #

@app.get("/")
def home():
    return {"message": "Fraud Detection API running 🚀"}