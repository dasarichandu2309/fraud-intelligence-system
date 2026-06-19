from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import get_connection
from jose import jwt, JWTError
from pydantic import BaseModel
import datetime
import hashlib
import joblib
import numpy as np

app = FastAPI()

# CONFIG
security = HTTPBearer()
SECRET_KEY = "supersecretkey"
ALGORITHM = "HS256"

# LOAD MODELS
fraud_model = joblib.load("fraud_model.pkl")
anomaly_model = joblib.load("anomaly_model.pkl")

# PASSWORD
def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str):
    return hashlib.sha256(password.encode()).hexdigest() == hashed

# AUTH
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        return jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# LOGIN
class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/login")
def login(data: LoginRequest):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE username=%s", (data.username,))
    user = cur.fetchone()

    cur.close()
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
    cur = conn.cursor()

    user_id = data.get("user_id")
    amount = data.get("amount", 0)
    hour = data.get("hour", 0)

    X = np.array([[amount, hour]])

    fraud_pred = fraud_model.predict(X)[0]
    prob = fraud_model.predict_proba(X)[0][1]

    anomaly_pred = anomaly_model.predict(X)[0]
    is_anomaly = 1 if anomaly_pred == -1 else 0

    # risk logic
    if fraud_pred == 1 and is_anomaly == 1:
        risk = "HIGH"
    elif fraud_pred == 1:
        risk = "MEDIUM"
    elif is_anomaly == 1:
        risk = "SUSPICIOUS"
    else:
        risk = "LOW"

    # save
    cur.execute(
        "INSERT INTO history (user_id, amount, hour, fraud, risk) VALUES (%s,%s,%s,%s,%s)",
        (user_id, amount, hour, int(fraud_pred), risk)
    )

    # ONLY blacklist (no email)
    if risk in ["HIGH", "MEDIUM"]:
        cur.execute(
            "INSERT INTO blacklist (user_id, reason) VALUES (%s,%s)",
            (user_id, "Fraud detected")
        )

    conn.commit()
    cur.close()
    conn.close()

    return {
        "fraud": int(fraud_pred),
        "anomaly": is_anomaly,
        "probability": float(prob),
        "risk": risk
    }

# ================= HISTORY ================= #
@app.get("/history/{user_id}")
def history(user_id: str, user=Depends(get_current_user)):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM history WHERE user_id=%s ORDER BY id DESC", (user_id,))
    data = cur.fetchall()

    cur.close()
    conn.close()

    return {"history": data}

# ================= ALERTS ================= #
@app.get("/alerts")
def alerts(user=Depends(get_current_user)):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, amount, risk, time
        FROM history
        WHERE fraud = 1
        ORDER BY time DESC
        LIMIT 10
    """)

    data = cur.fetchall()

    cur.close()
    conn.close()

    return {"alerts": data}

# ================= BLACKLIST ================= #
@app.post("/blacklist")
def blacklist(user_id: str, reason: str, user=Depends(get_current_user)):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("INSERT INTO blacklist (user_id, reason) VALUES (%s,%s)", (user_id, reason))

    conn.commit()
    cur.close()
    conn.close()

    return {"message": "Blacklisted"}

@app.delete("/blacklist/{user_id}")
def remove(user_id: str, user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM blacklist WHERE user_id=%s", (user_id,))
    conn.commit()

    cur.close()
    conn.close()

    return {"message": "Removed"}

# ROOT
@app.get("/")
def home():
    return {"message": "Fraud Detection API running 🚀"}