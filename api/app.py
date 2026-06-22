# ================= IMPORTS ================= #
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import get_connection
from jose import jwt
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

    model_only = fraud_model.named_steps["model"]
    explainer = shap.TreeExplainer(model_only)

    print("✅ Models + SHAP loaded")

except Exception as e:
    print("❌ Load failed:", e)
    fraud_model = None
    anomaly_model = None
    explainer = None

# ================= SCHEMAS ================= #
class LoginRequest(BaseModel):
    username: str
    password: str

class PredictRequest(BaseModel):
    user_id: int
    amount: float
    hour: int

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 1,
                "amount": 5000,
                "hour": 14
            }
        }

class TransactionRequest(BaseModel):
    user_id: int
    amount: float
    hour: int

# ================= PASSWORD ================= #
def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()

# ================= AUTH ================= #
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials.strip()

        if token.startswith("Bearer "):
            token = token[7:]

        token = token.replace('"', '').replace("'", "")

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload

    except Exception as e:
        print("TOKEN ERROR:", e)
        raise HTTPException(status_code=401, detail="Invalid token")

# ================= LOGIN ================= #
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
        "sub": str(user_id),   # ✅ FIX
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
def predict(data: PredictRequest, user=Depends(get_current_user)):

    if fraud_model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")

    conn = get_connection()
    cur = conn.cursor()

    try:
        user_id = data.user_id if user["role"] == "admin" else int(user["sub"])
        amount = float(data.amount)
        hour = int(data.hour)

        now = datetime.datetime.now()

        day_of_week = now.weekday()
        is_weekend = int(day_of_week >= 5)
        is_night = int(hour < 6)

        # USER STATS
        cur.execute("SELECT AVG(amount), MAX(amount) FROM history WHERE user_id=%s", (user_id,))
        stats = cur.fetchone() or (0, 0)

        avg_amount = stats[0] or 0
        max_amount = stats[1] or 0

        # TRANSACTIONS
        cur.execute("SELECT COUNT(*) FROM history WHERE user_id=%s AND time >= NOW() - INTERVAL '1 hour'", (user_id,))
        txn_1hr = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM history WHERE user_id=%s AND time >= NOW() - INTERVAL '24 hours'", (user_id,))
        txn_24hr = cur.fetchone()[0] or 0

        # TIME GAP
        cur.execute("SELECT EXTRACT(EPOCH FROM (NOW() - MAX(time))) FROM history WHERE user_id=%s", (user_id,))
        gap = cur.fetchone()[0]
        time_gap = gap if gap else 0

        # INPUT
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

        # FEATURE ALIGN
        for col in features:
            if col not in input_df:
                input_df[col] = 0

        input_df = input_df[features]

        # PREDICT
        fraud_pred = int(fraud_model.predict(input_df)[0])
        prob = float(fraud_model.predict_proba(input_df)[0][1])

        anomaly_pred = anomaly_model.predict(input_df)[0]
        is_anomaly = int(anomaly_pred == -1)

        # SHAP SAFE
        try:
            shap_values = explainer.shap_values(input_df)

            if isinstance(shap_values, list) and len(shap_values) > 1:
                values = shap_values[1][0]
            else:
                values = shap_values[0]

            shap_result = sorted(
                [{"feature": features[i], "impact": float(values[i])} for i in range(len(features))],
                key=lambda x: abs(x["impact"]),
                reverse=True
            )
        except Exception as e:
            print("SHAP ERROR:", e)
            shap_result = []

    except Exception as e:
        print("PREDICT ERROR:", e)
        raise HTTPException(status_code=500, detail=str(e))

    # RISK
    if prob > 0.6:
        risk = "HIGH"
    elif prob > 0.3:
        risk = "MEDIUM"
    elif is_anomaly:
        risk = "SUSPICIOUS"
    else:
        risk = "LOW"

    # SAVE
    try:
        cur.execute(
            "INSERT INTO history (user_id, amount, hour, fraud, risk) VALUES (%s,%s,%s,%s,%s)",
            (user_id, amount, hour, fraud_pred, str(risk))
        )

        if risk == "HIGH":
            cur.execute(
                "INSERT INTO blacklist (user_id, reason) VALUES (%s,%s)",
                (user_id, "High risk fraud")
            )

        conn.commit()

    except Exception as e:
        print("DB ERROR:", e)

    finally:
        cur.close()
        conn.close()

    return {
        "fraud": fraud_pred,
        "anomaly": is_anomaly,
        "probability": prob,
        "risk": risk,
        "explanation": shap_result[:5]
    }

# ================= ALERTS ================= #
@app.get("/alerts")
def alerts(user=Depends(get_current_user)):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, amount, risk, time
        FROM history
        ORDER BY time DESC
        LIMIT 20
    """)

    data = cur.fetchall()

    cur.close()
    conn.close()

    return {"alerts": data}

# ================= HISTORY ================= #
@app.get("/history/{user_id}")
def history(user_id: int, user=Depends(get_current_user)):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM history WHERE user_id=%s ORDER BY id DESC", (user_id,))
    data = cur.fetchall()

    cur.close()
    conn.close()

    return {"history": data}

# ================= BLACKLIST ================= #
@app.post("/blacklist")
def blacklist(user_id: int, reason: str, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("INSERT INTO blacklist (user_id, reason) VALUES (%s,%s)", (user_id, reason))

    conn.commit()
    cur.close()
    conn.close()

    return {"message": "User blacklisted"}

@app.delete("/blacklist/{user_id}")
def remove(user_id: int, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM blacklist WHERE user_id=%s", (user_id,))
    conn.commit()

    cur.close()
    conn.close()

    return {"message": "Removed from blacklist"}

# ================= ADD TRANSACTION ================= #
@app.post("/add_transaction")
def add_transaction(data: TransactionRequest, user=Depends(get_current_user)):

    conn = get_connection()
    cur = conn.cursor()

    user_id = data.user_id if user["role"] == "admin" else int(user["sub"])

    try:
        cur.execute(
            "INSERT INTO history (user_id, amount, hour, fraud, risk) VALUES (%s,%s,%s,%s,%s)",
            (user_id, data.amount, data.hour, 0, "NORMAL")
        )

        conn.commit()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cur.close()
        conn.close()

    return {"message": "Transaction added"}

# ================= AUDIT LOGS ================= #
@app.get("/audit_logs")
def audit_logs(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT user_id, amount, risk, time FROM history ORDER BY time DESC LIMIT 50")
    logs = cur.fetchall()

    cur.close()
    conn.close()

    return {"logs": logs}

# ================= ROOT ================= #
@app.get("/")
def home():
    return {"message": "Fraud Detection API running 🚀"}