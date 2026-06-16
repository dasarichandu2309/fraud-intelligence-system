from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from db import get_connection
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
import random

app = FastAPI()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = "supersecretkey"
ALGORITHM = "HS256"
security = HTTPBearer()


def verify_password(plain, hashed):
    return pwd_context.verify(plain[:72], hashed)


def verify_token(credentials=Depends(security)):
    try:
        token = credentials.credentials.strip().replace('"', '')

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload

    except Exception as e:
        print("JWT ERROR:", str(e))
        raise HTTPException(status_code=401, detail="Invalid token")


@app.post("/login")
def login(username: str, password: str):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cursor.fetchone()

    if not user or not verify_password(password, user[2]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = jwt.encode({
        "sub": username,
        "role": user[3],
        "exp": datetime.utcnow() + timedelta(hours=2)
    }, SECRET_KEY, algorithm=ALGORITHM)

    conn.close()
    return {"access_token": token}


class Transaction(BaseModel):
    user_id: int
    amount: float
    hour: int


@app.post("/predict")
def predict(data: Transaction, user=Depends(verify_token)):

    conn = get_connection()
    cursor = conn.cursor()

    # blacklist check
    cursor.execute("SELECT * FROM blacklist WHERE user_id=%s", (data.user_id,))
    if cursor.fetchone():
        conn.close()
        return {"error": "User is blacklisted"}

    fraud = 1 if data.amount > 15000 else 0
    risk = random.randint(1, 5)

    explanation = {
        "amount": round(random.uniform(-1, 1), 3),
        "hour": round(random.uniform(-1, 1), 3)
    }

    # save
    cursor.execute("""
    INSERT INTO history (user_id, amount, hour, fraud, risk)
    VALUES (%s, %s, %s, %s, %s)
    """, (data.user_id, data.amount, data.hour, fraud, risk))

    # audit log
    cursor.execute("""
    INSERT INTO audit_logs (username, action, amount, fraud)
    VALUES (%s, %s, %s, %s)
    """, (user["sub"], "predict", data.amount, fraud))

    conn.commit()
    conn.close()

    return {
        "fraud": fraud,
        "risk": risk,
        "explanation": explanation
    }


@app.get("/history/{user_id}")
def history(user_id: int, user=Depends(verify_token)):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT amount, hour, fraud, risk, time
    FROM history WHERE user_id=%s ORDER BY time DESC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    return {"history": [
        {"amount": r[0], "hour": r[1], "fraud": r[2], "risk": r[3], "time": r[4]}
        for r in rows
    ]}


@app.get("/audit_logs")
def audit_logs(user=Depends(verify_token)):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT username, action, amount, fraud, time
    FROM audit_logs ORDER BY time DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    return {"logs": [
        {"user": r[0], "action": r[1], "amount": r[2], "fraud": r[3], "time": r[4]}
        for r in rows
    ]}