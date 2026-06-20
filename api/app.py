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
try:
    fraud_model = joblib.load("fraud_model.pkl")
    anomaly_model = joblib.load("anomaly_model.pkl")
    print("✅ Models loaded successfully")
except Exception as e:
    print("❌ Model load failed:", e)
    fraud_model = None
    anomaly_model = None

# ================= PASSWORD ================= #
def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()

# ================= AUTH ================= #
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
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
    cur = conn.cursor()

    cur.execute("SELECT username, password, role FROM users WHERE username=%s", (data.username.strip(),))
    user = cur.fetchone()

    cur.close()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    username, db_password, role = user

    input_hash = hashlib.sha256(data.password.encode()).hexdigest().strip()
    db_hash = str(db_password).strip()

    print("INPUT HASH:", input_hash)
    print("DB HASH:", db_hash)

    if input_hash != db_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = jwt.encode({
        "sub": username,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=5)
    }, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "access_token": token,
        "user": username,
        "role": role
    }

# ================= PREDICT ================= #
@app.post("/predict")
def predict(data: dict, user=Depends(get_current_user)):

    if fraud_model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")

    conn = get_connection()
    cur = conn.cursor()

    user_id = data.get("user_id")
    amount = float(data.get("amount", 0))
    hour = int(data.get("hour", 0))

    try:
        # 🔥 FIX: match model expected 6 features
        X = np.array([[amount, hour, 0, 0, 0, 0]])

        fraud_pred = int(fraud_model.predict(X)[0])
        prob = float(fraud_model.predict_proba(X)[0][1])

        anomaly_pred = anomaly_model.predict(X)[0]
        is_anomaly = 1 if anomaly_pred == -1 else 0

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # ================= RISK LOGIC ================= #
    if prob > 0.8:
        risk = "HIGH"
    elif prob > 0.5:
        risk = "MEDIUM"
    elif is_anomaly:
        risk = "SUSPICIOUS"
    else:
        risk = "LOW"

    # ================= SAVE ================= #
    cur.execute(
        "INSERT INTO history (user_id, amount, hour, fraud, risk) VALUES (%s,%s,%s,%s,%s)",
        (user_id, amount, hour, fraud_pred, risk)
    )

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

    cur.execute("INSERT INTO blacklist (user_id, reason) VALUES (%s,%s)", (user_id, reason))

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

# ================= ROOT ================= #
@app.get("/")
def home():
    return {"message": "Fraud Detection API running 🚀"}