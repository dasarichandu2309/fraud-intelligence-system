import streamlit as st
import requests
import pandas as pd
from jose import jwt

API_URL = "https://fraud-api-mcgb.onrender.com"

st.set_page_config(layout="wide")

# ================= SESSION ================= #
if "token" not in st.session_state:
    st.session_state.token = None

if "role" not in st.session_state:
    st.session_state.role = None

st.title("🏦 Fraud Detection System")

# ================= LOGIN ================= #
if st.session_state.token is None:

    st.subheader("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        if not username or not password:
            st.error("Enter credentials")
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

                    st.success("Login success ✅")
                    st.rerun()
                else:
                    st.error("Invalid credentials ❌")

            except Exception as e:
                st.error(f"Error: {e}")

    # 🚨 CRITICAL LINE
    st.stop()

# ================= DASHBOARD ================= #

headers = {"Authorization": f"Bearer {st.session_state.token}"}

menu = st.sidebar.selectbox(
    "Menu",
    ["Predict", "History", "Audit Logs", "Logout"]
)

# ================= PREDICT ================= #
if menu == "Predict":

    amount = st.number_input("Amount", 0.0)
    hour = st.slider("Hour", 0, 23)

    if st.button("Predict"):

        res = requests.post(
            f"{API_URL}/predict",
            json={
                "amount": amount,
                "hour": hour
            },
            headers=headers
        )

        if res.status_code == 200:
            result = res.json()

            if result["fraud"]:
                st.error("🚨 Fraud Detected")
            else:
                st.success("✅ Safe")

            st.write(f"Risk: {result['risk']}")
        else:
            st.error("Unauthorized ❌")

# ================= HISTORY ================= #
elif menu == "History":

    res = requests.get(f"{API_URL}/history", headers=headers)

    if res.status_code == 200:
        data = res.json().get("history", [])
        st.dataframe(pd.DataFrame(data))
    else:
        st.error("Failed to fetch")

# ================= AUDIT ================= #
elif menu == "Audit Logs":

    res = requests.get(f"{API_URL}/audit_logs", headers=headers)

    if res.status_code == 200:
        logs = res.json().get("logs", [])
        st.dataframe(pd.DataFrame(logs))
    else:
        st.error("Failed")

# ================= LOGOUT ================= #
elif menu == "Logout":
    st.session_state.token = None
    st.session_state.role = None
    st.rerun()