from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import get_connection
from passlib.context import CryptContext
from jose import jwt, JWTError
import datetime

app = FastAPI()

# 🔐 Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

SECRET_KEY = "supersecretkey"
ALGORITHM = "HS256"


# ================= PASSWORD ================= #

def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)


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

@app.post("/login")
def login(username: str, password: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(password, user[2]):
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

    # Dummy fraud logic (replace with ML later)
    amount = data.get("amount", 0)
    fraud = amount > 10000

    cursor.execute(
        "INSERT INTO transactions (user_id, amount, fraud) VALUES (%s, %s, %s)",
        (user["sub"], amount, fraud)
    )

    conn.commit()

    cursor.close()
    conn.close()

    return {"fraud": fraud}


# ================= HISTORY ================= #

@app.get("/history")
def get_history(user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM transactions WHERE user_id=%s",
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
def blacklist_user(user_id: int, reason: str, user=Depends(get_current_user)):
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
def remove_blacklist(user_id: int, user=Depends(get_current_user)):
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
@app.post("/transaction")
def add_transaction(amount: float, user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    fraud = amount > 10000  # simple rule

    cursor.execute(
        "INSERT INTO transactions (user_id, amount, fraud) VALUES (%s, %s, %s)",
        (user["sub"], amount, fraud)
    )

    conn.commit()

    cursor.close()
    conn.close()

    return {
        "message": "Transaction added",
        "fraud": fraud
    }

# ================= ROOT ================= #

@app.get("/")
def home():
    return {"message": "Fraud Detection API running 🚀"}