from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import get_connection
from jose import jwt, JWTError
from pydantic import BaseModel
import datetime
import hashlib
import joblib
import pandas as pd
import shap

app = FastAPI()

# ================= CONFIG ================= #
security = HTTPBearer()
SECRET_KEY = "supersecretkey"
ALGORITHM = "HS256"

# ================= LOAD MODELS ================= #
try:
    data = joblib.load("fraud_model.pkl")
    fraud_model = data["model"]
    features = data["features"]

    anomaly_model = joblib.load("anomaly_model.pkl")

    explainer = shap.Explainer(fraud_model)

    print("✅ Models + SHAP loaded")

except Exception as e:
    print("❌ Load failed:", e)
    fraud_model = None
    anomaly_model = None
    explainer = None

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

    cur.execute("SELECT id, username, password, role FROM users WHERE username=%s", (data.username.strip(),))
    user = cur.fetchone()

    cur.close()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    user_id, username, db_password, role = user

    if hash_password(data.password) != str(db_password).strip():
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = jwt.encode({
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=5)
    }, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "access_token": token,
        "user_id": user_id,
        "username": username,
        "role": role
    }

# ================= PREDICT ================= #
@app.post("/predict")
def predict(data: dict, user=Depends(get_current_user)):

    if fraud_model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")

    conn = get_connection()
    cur = conn.cursor()

    # ===== USER ID =====
    if user["role"] == "admin":
        user_id = int(data.get("user_id", user["sub"]))
    else:
        user_id = int(user["sub"])

    amount = float(data.get("amount", 0))
    hour = int(data.get("hour", 0))

    try:
        now = datetime.datetime.now()

        day_of_week = now.weekday()
        is_weekend = 1 if day_of_week >= 5 else 0
        is_night = 1 if hour < 6 else 0

        # ===== USER STATS =====
        cur.execute("""
            SELECT AVG(amount), MAX(amount)
            FROM history WHERE user_id=%s
        """, (user_id,))
        stats = cur.fetchone()

        avg_amount = stats[0] or 0
        max_amount = stats[1] or 0

        # ===== TRANSACTIONS =====
        cur.execute("""
            SELECT COUNT(*) FROM history 
            WHERE user_id=%s AND time >= NOW() - INTERVAL '1 hour'
        """, (user_id,))
        txn_1hr = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM history 
            WHERE user_id=%s AND time >= NOW() - INTERVAL '24 hours'
        """, (user_id,))
        txn_24hr = cur.fetchone()[0]

        # ===== TIME GAP =====
        cur.execute("""
            SELECT EXTRACT(EPOCH FROM (NOW() - MAX(time)))
            FROM history WHERE user_id=%s
        """, (user_id,))
        gap = cur.fetchone()[0]

        time_gap = gap if gap else 0

        # ===== INPUT =====
        input_df = pd.DataFrame([{
            "Amount": amount,
            "hour": hour,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "transactions_last_1hr": txn_1hr,
            "transactions_last_24hr": txn_24hr,
            "avg_user_amount": avg_amount,
            "max_user_amount": max_amount,
            "time_since_last_txn": time_gap,
            "is_night": is_night,
            "high_amount_flag": int(amount > avg_amount),
            "amount_deviation": amount - avg_amount
        }])

        # 🔥 match model features
        input_df = input_df[features]

        # ===== PREDICTIONS =====
        fraud_pred = int(fraud_model.predict(input_df)[0])
        prob = float(fraud_model.predict_proba(input_df)[0][1])

        anomaly_pred = anomaly_model.predict(input_df)[0]
        is_anomaly = 1 if anomaly_pred == -1 else 0

        # ===== SHAP =====
        shap_values = explainer(input_df)
        values = shap_values.values[0]

        shap_result = [
            {"feature": features[i], "impact": float(values[i])}
            for i in range(len(features))
        ]

        shap_result = sorted(shap_result, key=lambda x: abs(x["impact"]), reverse=True)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # ===== RISK =====
    if prob > 0.8:
        risk = "HIGH"
    elif prob > 0.5:
        risk = "MEDIUM"
    elif is_anomaly:
        risk = "SUSPICIOUS"
    else:
        risk = "LOW"

    # ===== SAVE =====
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
        "risk": risk,
        "explanation": shap_result[:5]
    }

# ================= ROOT ================= #
@app.get("/")
def home():
    return {"message": "Fraud Detection API running 🚀"}