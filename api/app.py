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
    device_id: str = "web"
    location: str = "IN"

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

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload

    except Exception:
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
        "sub": str(user_id),
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
        device_id = data.device_id
        location = data.location

        now = datetime.datetime.now()

        day_of_week = now.weekday()
        is_weekend = int(day_of_week >= 5)
        is_night = int(hour < 6)

        # ================= USER STATS ================= #
        cur.execute("SELECT AVG(amount), MAX(amount) FROM history WHERE user_id=%s", (user_id,))
        stats = cur.fetchone() or (0, 0)

        avg_amount = stats[0] or 1
        max_amount = stats[1] or 0

        # ================= TRANSACTIONS ================= #
        cur.execute("SELECT COUNT(*) FROM history WHERE user_id=%s AND time >= NOW() - INTERVAL '1 hour'", (user_id,))
        txn_1hr = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM history WHERE user_id=%s AND time >= NOW() - INTERVAL '24 hours'", (user_id,))
        txn_24hr = cur.fetchone()[0] or 0

        # ================= DEVICE ================= #
        cur.execute("SELECT COUNT(*) FROM history WHERE user_id=%s AND device_id=%s", (user_id, device_id))
        device_used_before = cur.fetchone()[0]
        new_device = 1 if device_used_before == 0 else 0

        # ================= GEO ================= #
        geo_risk = 1 if location != "IN" else 0

        # ================= MODEL INPUT ================= #
        input_df = pd.DataFrame([{
            "Amount": amount,
            "hour": hour,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "transactions_last_1hr": txn_1hr,
            "transactions_last_24hr": txn_24hr,
            "avg_user_amount": avg_amount,
            "max_user_amount": max_amount,
            "time_since_last_txn": 0,
            "is_night": is_night,
            "high_amount_flag": int(amount > avg_amount),
            "amount_deviation": amount - avg_amount
        }])

        for col in features:
            if col not in input_df:
                input_df[col] = 0

        input_df = input_df[features]

        fraud_pred = int(fraud_model.predict(input_df)[0])
        prob = float(fraud_model.predict_proba(input_df)[0][1])

        anomaly_pred = anomaly_model.predict(input_df)[0]
        is_anomaly = int(anomaly_pred == -1)

        # ================= SHAP FIX ================= #
        try:
            shap_values = explainer.shap_values(input_df)

            if isinstance(shap_values, list):
                values = shap_values[1] if len(shap_values) > 1 else shap_values[0]
            else:
                values = shap_values

            values = pd.DataFrame(values).values
            values = values[0] if len(values.shape) > 1 else values

            shap_result = sorted(
                [
                    {
                        "feature": features[i],
                        "impact": float(values[i]) if i < len(values) else 0.0
                    }
                    for i in range(len(features))
                ],
                key=lambda x: abs(x["impact"]),
                reverse=True
            )

        except Exception as e:
            print("SHAP ERROR FIXED:", e)
            shap_result = []

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # ================= BANKING RISK ================= #
    risk_score = 0
    reasons = []

    if prob > 0.8:
        risk_score += 50; reasons.append("High ML fraud probability")
    elif prob > 0.5:
        risk_score += 30; reasons.append("Moderate ML fraud probability")

    if amount > avg_amount * 3:
        risk_score += 30; reasons.append("Huge amount spike")
    elif amount > avg_amount * 2:
        risk_score += 20; reasons.append("High amount")

    if txn_1hr > 5:
        risk_score += 25; reasons.append("High transaction velocity")

    if is_night:
        risk_score += 10; reasons.append("Night transaction")

    if is_anomaly:
        risk_score += 25; reasons.append("Anomaly detected")

    if geo_risk:
        risk_score += 30; reasons.append("Unusual location")

    if new_device:
        risk_score += 20; reasons.append("New device used")

    if risk_score >= 80:
        risk = "HIGH"
    elif risk_score >= 50:
        risk = "MEDIUM"
    elif risk_score >= 25:
        risk = "SUSPICIOUS"
    else:
        risk = "LOW"

    # ================= SAVE ================= #
    cur.execute(
        """INSERT INTO history 
        (user_id, amount, hour, fraud, risk, device_id, location)
        VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (user_id, amount, hour, fraud_pred, risk, device_id, location)
    )

    # ================= SMART AUTO BLACKLIST ================= #
    if risk == "HIGH":
        try:
            cur.execute(
                "SELECT COUNT(*) FROM history WHERE user_id=%s AND risk='HIGH'",
                (user_id,)
            )
            count = cur.fetchone()[0] or 0

            if count >= 2:
                cur.execute(
                    "INSERT INTO blacklist (user_id, reason) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                    (user_id, "multiple_high_risk")
                )

        except Exception as e:
            print("AUTO BLACKLIST ERROR:", e)

    conn.commit()
    cur.close()
    conn.close()

    return {
        "fraud": fraud_pred,
        "probability": prob,
        "risk": risk,
        "risk_score": risk_score,
        "reasons": reasons,
        "anomaly": is_anomaly,
        "explanation": shap_result[:5]
    }

# ================= OTHER ROUTES ================= #
@app.get("/blacklist")
def get_blacklist(user=Depends(get_current_user)):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id, reason FROM blacklist")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return {"blacklist": rows}

@app.post("/blacklist")
def blacklist(user_id: int, reason: str, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO blacklist (user_id, reason) VALUES (%s,%s)", (user_id, reason))
    conn.commit()
    cur.close(); conn.close()
    return {"message": "User blacklisted"}

@app.delete("/blacklist/{user_id}")
def remove(user_id: int, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM blacklist WHERE user_id=%s", (user_id,))
    conn.commit()
    cur.close(); conn.close()
    return {"message": "Removed from blacklist"}