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

# ================= CONFIG ================= #
security = HTTPBearer()
SECRET_KEY = "supersecretkey"
ALGORITHM = "HS256"

# ================= LOAD MODELS ================= #
fraud_model = joblib.load("fraud_model.pkl")
anomaly_model = joblib.load("anomaly_model.pkl")

# ================= PASSWORD ================= #
def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str):
    return hash_password(password) == hashed.strip()

# ================= AUTH ================= #
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# ================= LOGIN ================= #
class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/login")
def login(data: LoginRequest):

    conn = get_connection()
    cur = conn.cursor()

    # 🔥 FIX: trim username
    cur.execute("SELECT * FROM users WHERE username=%s", (data.username.strip(),))
    user = cur.fetchone()

    cur.close()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # 🔥 DEBUG SAFE CHECK
    if not verify_password(data.password, user[2]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = jwt.encode({
        "sub": user[1],
        "role": user[3],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=5)
    }, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "access_token": token,
        "user": user[1],
        "role": user[3]
    }

# ================= PREDICT ================= #
@app.post("/predict")
def predict(data: dict, user=Depends(get_current_user)):

    conn = get_connection()
    cur = conn.cursor()

    user_id = data.get("user_id")
    amount = float(data.get("amount", 0))
    hour = int(data.get("hour", 0))

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")

    X = np.array([[amount, hour]])

    fraud_pred = int(fraud_model.predict(X)[0])
    prob = float(fraud_model.predict_proba(X)[0][1])

    anomaly_pred = anomaly_model.predict(X)[0]
    is_anomaly = 1 if anomaly_pred == -1 else 0

    # 🔥 BETTER RISK LOGIC
    if prob > 0.8:
        risk = "HIGH"
    elif prob > 0.5:
        risk = "MEDIUM"
    elif is_anomaly:
        risk = "SUSPICIOUS"
    else:
        risk = "LOW"

    # SAVE HISTORY
    cur.execute(
        "INSERT INTO history (user_id, amount, hour, fraud, risk) VALUES (%s,%s,%s,%s,%s)",
        (user_id, amount, hour, fraud_pred, risk)
    )

    # AUTO BLACKLIST
    if risk == "HIGH":
        cur.execute(
            "INSERT INTO blacklist (user_id, reason) VALUES (%s,%s)",
            (user_id, "High risk fraud")
        )

    conn.commit()
    cur.close()
    conn.close()

    return {
        "fraud": fraud_pred,
        "anomaly": is_anomaly,
        "probability": prob,
        "risk": risk
    }

# ================= HISTORY ================= #
@app.get("/history/{user_id}")
def history(user_id: str, user=Depends(get_current_user)):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM history WHERE user_id=%s ORDER BY id DESC",
        (user_id,)
    )
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
        WHERE risk IN ('HIGH','MEDIUM')
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

    cur.execute(
        "INSERT INTO blacklist (user_id, reason) VALUES (%s,%s)",
        (user_id, reason)
    )

    conn.commit()
    cur.close()
    conn.close()

    return {"message": "User blacklisted"}

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

    return {"message": "Removed from blacklist"}

# ================= DEBUG ================= #
@app.get("/debug_users")
def debug_users():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, username, role FROM users")
    data = cur.fetchall()

    cur.close()
    conn.close()

    return {"users": data}

# ================= ROOT ================= #
@app.get("/")
def home():
    return {"message": "Fraud Detection API running 🚀"}