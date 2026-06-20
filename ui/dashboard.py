import streamlit as st
import requests
import pandas as pd
from jose import jwt, JWTError
import time

API_URL = "https://fraud-api-mcgb.onrender.com"

st.set_page_config(page_title="Fraud Intelligence System", layout="wide")

# ================= SESSION ================= #
if "token" not in st.session_state:
    st.session_state.token = None
if "role" not in st.session_state:
    st.session_state.role = None
if "user" not in st.session_state:
    st.session_state.user = None

st.title("🏦 Fraud Intelligence System")

# ================= LOGIN ================= #
if st.session_state.token is None:

    st.subheader("🔐 Secure Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        if not username or not password:
            st.warning("Enter username & password")
        else:
            try:
                res = requests.post(
                    f"{API_URL}/login",
                    json={"username": username, "password": password}
                )

                if res.status_code == 200:
                    token = res.json()["access_token"]
                    st.session_state.token = token

                    decoded = jwt.decode(token, "supersecretkey", algorithms=["HS256"])
                    st.session_state.role = decoded.get("role")
                    st.session_state.user = decoded.get("sub")

                    st.success("Login successful ✅")
                    st.rerun()

                elif res.status_code == 401:
                    st.error("Invalid username or password ❌")

                else:
                    st.error("Server error")

            except Exception as e:
                st.error(f"Connection error: {e}")

    st.stop()

# ================= TOKEN CHECK ================= #
headers = {"Authorization": f"Bearer {st.session_state.token}"}

# 🔥 AUTO LOGOUT IF TOKEN EXPIRED
try:
    jwt.decode(st.session_state.token, "supersecretkey", algorithms=["HS256"])
except JWTError:
    st.session_state.token = None
    st.error("Session expired. Login again.")
    st.rerun()

# ================= SIDEBAR ================= #
st.sidebar.title("🧠 Fraud Dashboard")
st.sidebar.write(f"👤 User: {st.session_state.user}")
st.sidebar.write(f"🔐 Role: {st.session_state.role}")

# 🔥 ROLE-BASED MENU
menu_options = ["Predict", "Alerts", "History"]

if st.session_state.role == "admin":
    menu_options.append("Blacklist")

menu_options.append("Logout")

menu = st.sidebar.selectbox("Menu", menu_options)

# ================= USER INPUT ================= #
user_id = st.sidebar.text_input("Customer User ID", "user1")

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

        if res.status_code == 401:
            st.error("Session expired")
            st.session_state.token = None
            st.rerun()

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

# ================= ALERTS ================= #
elif menu == "Alerts":

    st.title("🚨 Live Fraud Alerts")

    res = requests.get(f"{API_URL}/alerts", headers=headers)

    if res.status_code == 401:
        st.session_state.token = None
        st.rerun()

    alerts = res.json().get("alerts", [])

    if alerts:
        df = pd.DataFrame(alerts, columns=["User", "Amount", "Risk", "Time"])
        st.dataframe(df)

        for row in alerts:
            if row[2] == "HIGH":
                st.error(f"🚨 HIGH: {row[0]} ₹{row[1]}")
    else:
        st.success("No fraud alerts")

    # 🔥 AUTO REFRESH
    time.sleep(3)
    st.rerun()

# ================= HISTORY ================= #
elif menu == "History":

    st.subheader("📜 Transaction History")

    res = requests.get(f"{API_URL}/history/{user_id}", headers=headers)

    if res.status_code == 401:
        st.session_state.token = None
        st.rerun()

    data = res.json().get("history", [])
    st.dataframe(pd.DataFrame(data))

# ================= BLACKLIST (ADMIN ONLY) ================= #
elif menu == "Blacklist":

    st.subheader("🚫 Blacklist Control")

    if st.session_state.role != "admin":
        st.error("Access Denied")
        st.stop()

    if st.button("Add to Blacklist"):
        requests.post(
            f"{API_URL}/blacklist",
            params={"user_id": user_id, "reason": "manual"},
            headers=headers
        )
        st.success("User Blacklisted")

    if st.button("Remove from Blacklist"):
        requests.delete(
            f"{API_URL}/blacklist/{user_id}",
            headers=headers
        )
        st.success("Removed from Blacklist")

# ================= LOGOUT ================= #
elif menu == "Logout":
    st.session_state.clear()
    st.success("Logged out")
    st.rerun()