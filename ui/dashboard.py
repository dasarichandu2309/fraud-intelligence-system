import streamlit as st
import requests
import pandas as pd
from jose import jwt

API_URL = "https://fraud-api-mcgb.onrender.com"

st.set_page_config(page_title="Fraud Detection", layout="wide")

# ================= SESSION ================= #
if "token" not in st.session_state:
    st.session_state.token = None

if "role" not in st.session_state:
    st.session_state.role = None

# ================= TITLE ================= #
st.title("🏦 Fraud Detection System")

# ================= LOGIN ================= #
if st.session_state.token is None:

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.subheader("🔐 Login")

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login", use_container_width=True):

            if not username or not password:
                st.warning("Enter username and password")
            else:
                try:
                    res = requests.post(
                        f"{API_URL}/login",
                        json={
                            "username": username,
                            "password": password
                        }
                    )

                    if res.status_code == 200:
                        token = res.json()["access_token"]
                        st.session_state.token = token

                        decoded = jwt.decode(token, "supersecretkey", algorithms=["HS256"])
                        st.session_state.role = decoded.get("role", "user")

                        st.success("Login successful ✅")
                        st.rerun()
                    else:
                        st.error("Invalid credentials ❌")

                except Exception as e:
                    st.error(f"Error: {e}")

    st.stop()

# ================= DASHBOARD ================= #

headers = {"Authorization": f"Bearer {st.session_state.token}"}

decoded = jwt.decode(st.session_state.token, "supersecretkey", algorithms=["HS256"])
user_id = decoded["sub"]

# Sidebar
st.sidebar.title("📊 Dashboard")
st.sidebar.write(f"👤 User: {user_id}")
st.sidebar.write(f"🔐 Role: {st.session_state.role}")

menu = st.sidebar.selectbox(
    "Menu",
    ["Predict", "Add Transaction", "History", "Audit Logs", "Logout"]
)

# ================= PREDICT ================= #
if menu == "Predict":

    st.subheader("💳 Fraud Prediction")

    st.write(f"User ID: **{user_id}**")

    col1, col2 = st.columns(2)

    with col1:
        amount = st.number_input("Amount", 0.0)

    with col2:
        hour = st.slider("Hour", 0, 23)

    if st.button("Check Fraud", use_container_width=True):

        res = requests.post(
            f"{API_URL}/predict",
            json={"amount": amount, "hour": hour},
            headers=headers
        )

        if res.status_code == 200:
            result = res.json()

            if result["fraud"]:
                st.error("🚨 Fraud Detected")
            else:
                st.success("✅ Safe Transaction")

            st.info(f"Risk Level: {result['risk']}")

            if result.get("alert"):
                st.warning(result["alert"])

        else:
            st.error("Unauthorized ❌")


# ================= ADD TRANSACTION ================= #
elif menu == "Add Transaction":

    st.subheader("➕ Add Transaction")

    st.write(f"User ID: **{user_id}**")

    amount = st.number_input("Transaction Amount", 0.0)

    if st.button("Add Transaction", use_container_width=True):

        res = requests.post(
            f"{API_URL}/transaction",
            params={"amount": amount},
            headers=headers
        )

        if res.status_code == 200:
            result = res.json()

            st.success("Transaction added successfully ✅")

            if result["fraud"]:
                st.warning("⚠️ This transaction is flagged as fraud")

        else:
            st.error("Failed to add transaction ❌")


# ================= HISTORY ================= #
elif menu == "History":

    st.subheader("📜 Transaction History")

    st.write(f"User ID: **{user_id}**")

    res = requests.get(f"{API_URL}/history", headers=headers)

    if res.status_code == 200:
        data = res.json().get("history", [])
        st.dataframe(pd.DataFrame(data), use_container_width=True)
    else:
        st.error("Failed to fetch history")


# ================= AUDIT LOGS ================= #
elif menu == "Audit Logs":

    st.subheader("🧾 Audit Logs")

    res = requests.get(f"{API_URL}/audit_logs", headers=headers)

    if res.status_code == 200:
        logs = res.json().get("logs", [])
        st.dataframe(pd.DataFrame(logs), use_container_width=True)
    else:
        st.error("Failed to fetch logs")


# ================= LOGOUT ================= #
elif menu == "Logout":

    st.session_state.token = None
    st.session_state.role = None
    st.success("Logged out successfully")
    st.rerun()