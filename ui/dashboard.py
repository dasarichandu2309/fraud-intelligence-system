import streamlit as st
import requests
import pandas as pd
from jose import jwt
import time

API_URL = "https://fraud-api-mcgb.onrender.com"

st.set_page_config(page_title="Fraud Intelligence System", layout="wide")

# ================= SESSION ================= #
if "token" not in st.session_state:
    st.session_state.token = None
if "role" not in st.session_state:
    st.session_state.role = None

st.title("🏦 Fraud Intelligence System")

# ================= LOGIN ================= #
if st.session_state.token is None:

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        res = requests.post(
            f"{API_URL}/login",
            json={"username": username, "password": password}
        )

        if res.status_code == 200:
            token = res.json()["access_token"]
            st.session_state.token = token

            decoded = jwt.decode(token, "supersecretkey", algorithms=["HS256"])
            st.session_state.role = decoded["role"]

            st.success("Login success")
            st.rerun()
        else:
            st.error("Invalid credentials")

    st.stop()

# ================= AUTH HEADER ================= #
headers = {"Authorization": f"Bearer {st.session_state.token}"}

st.sidebar.title("🧠 Fraud Intelligence")
st.sidebar.write(f"Role: {st.session_state.role}")

user_id = st.sidebar.text_input("Customer User ID", "user1")

menu = st.sidebar.selectbox(
    "Menu",
    ["Predict", "Alerts", "History", "Blacklist", "Logout"]
)

# ================= PREDICT ================= #
if menu == "Predict":

    st.subheader("🔍 Fraud Prediction")

    amount = st.number_input("Amount", 0.0)
    hour = st.slider("Hour", 0, 23)

    if st.button("Analyze Transaction"):

        res = requests.post(
            f"{API_URL}/predict",
            json={"user_id": user_id, "amount": amount, "hour": hour},
            headers=headers
        )

        result = res.json()

        prob = result["probability"]
        risk = result["risk"]

        # 🎯 Risk Display
        if risk == "HIGH":
            st.error("🔴 HIGH RISK FRAUD")
        elif risk == "MEDIUM":
            st.warning("🟠 MEDIUM RISK")
        elif risk == "SUSPICIOUS":
            st.info("🟡 SUSPICIOUS")
        else:
            st.success("🟢 SAFE")

        # 🎯 Probability Gauge
        st.progress(prob)
        st.metric("Fraud Probability", f"{prob*100:.2f}%")

        # 🎯 Model Outputs
        col1, col2 = st.columns(2)
        col1.metric("Fraud Model", result["fraud"])
        col2.metric("Anomaly Model", result["anomaly"])

# ================= ALERTS ================= #
elif menu == "Alerts":

    st.title("🚨 Live Fraud Alerts (Auto Refresh)")

    res = requests.get(f"{API_URL}/alerts", headers=headers)
    alerts = res.json().get("alerts", [])

    if not alerts:
        st.success("✅ No recent fraud activity")
    else:
        df = pd.DataFrame(alerts, columns=["User", "Amount", "Risk", "Time"])
        st.dataframe(df)

        st.subheader("⚠️ Highlights")

        for row in alerts:
            if row[2] == "HIGH":
                st.error(f"🚨 HIGH: {row[0]} | ₹{row[1]}")
            elif row[2] == "MEDIUM":
                st.warning(f"⚠️ MEDIUM: {row[0]} | ₹{row[1]}")

    # 🔥 AUTO REFRESH EVERY 3 SECONDS
    time.sleep(3)
    st.rerun()

# ================= HISTORY ================= #
elif menu == "History":

    st.subheader("📜 Transaction History")

    res = requests.get(f"{API_URL}/history/{user_id}", headers=headers)
    data = res.json().get("history", [])

    st.dataframe(pd.DataFrame(data))

# ================= BLACKLIST ================= #
elif menu == "Blacklist":

    st.subheader("🚫 Blacklist Management")

    if st.button("Add to Blacklist"):
        requests.post(
            f"{API_URL}/blacklist",
            params={"user_id": user_id, "reason": "manual"},
            headers=headers
        )
        st.success("User Blacklisted")

    if st.session_state.role == "admin":
        if st.button("Remove from Blacklist"):
            requests.delete(
                f"{API_URL}/blacklist/{user_id}",
                headers=headers
            )
            st.success("Removed from Blacklist")

# ================= LOGOUT ================= #
elif menu == "Logout":
    st.session_state.token = None
    st.session_state.role = None
    st.rerun()