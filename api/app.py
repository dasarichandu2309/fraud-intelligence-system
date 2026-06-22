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
    fraud_model = joblib.load("fraud_model.pkl")
    anomaly_model = joblib.load("anomaly_model.pkl")

    # 🔥 FIX: works with Pipeline also
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

    # 🔥 allow admin override
    if user["role"] == "admin":
        user_id = int(data.get("user_id", user["sub"]))
    else:
        user_id = int(user["sub"])

    amount = float(data.get("amount", 0))
    hour = int(data.get("hour", 0))

    try:
        # 🔥 input dataframe
        input_df = pd.DataFrame([{
            "amount": amount,
            "hour": hour,
            "f1": 0,
            "f2": 0,
            "f3": 0,
            "f4": 0
        }])

        # 🔥 prediction (pipeline handles scaling)
        fraud_pred = int(fraud_model.predict(input_df)[0])
        prob = float(fraud_model.predict_proba(input_df)[0][1])

        anomaly_pred = anomaly_model.predict(input_df)[0]
        is_anomaly = 1 if anomaly_pred == -1 else 0

        # ================= SHAP ================= #
        shap_values = explainer(input_df)

        values = shap_values.values[0]
        feature_names = input_df.columns.tolist()

        shap_result = []
        for i in range(len(feature_names)):
            shap_result.append({
                "feature": feature_names[i],
                "impact": float(values[i])
            })

        shap_result = sorted(shap_result, key=lambda x: abs(x["impact"]), reverse=True)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # ================= RISK ================= #
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
        "risk": risk,
        "explanation": shap_result[:5]
    }

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

# ================= ROOT ================= #
@app.get("/")
def home():
    return {"message": "Fraud Detection API running 🚀"}