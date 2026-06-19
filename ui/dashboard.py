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

# ================= DASHBOARD ================= #

headers = {"Authorization": f"Bearer {st.session_state.token}"}

st.sidebar.title("Dashboard")
st.sidebar.write(f"Role: {st.session_state.role}")

# 🔥 USER INPUT
user_id = st.sidebar.text_input("Customer User ID", value="user1")

menu = st.sidebar.selectbox(
    "Menu",
    ["Predict", "Add Transaction", "History", "Blacklist", "Logout"]
)

# ================= PREDICT ================= #
if menu == "Predict":

    st.subheader("Fraud Prediction")

    amount = st.number_input("Amount", 0.0)
    hour = st.slider("Hour", 0, 23)

    if st.button("Predict"):

        res = requests.post(
            f"{API_URL}/predict",
            json={"user_id": user_id, "amount": amount, "hour": hour},
            headers=headers
        )

        if res.status_code == 200:
            result = res.json()

            if result["fraud"]:
                st.error("Fraud Detected")
            else:
                st.success("Safe")

            st.write("Risk:", result["risk"])
        else:
            st.error("Error")

# ================= TRANSACTION ================= #
elif menu == "Add Transaction":

    amount = st.number_input("Amount", 0.0)

    if st.button("Add Transaction"):

        res = requests.post(
            f"{API_URL}/transaction",
            json={"user_id": user_id, "amount": amount},
            headers=headers
        )

        if res.status_code == 200:
            st.success("Transaction added")
        else:
            st.error("Failed")

# ================= HISTORY ================= #
elif menu == "History":

    res = requests.get(f"{API_URL}/history/{user_id}", headers=headers)

    if res.status_code == 200:
        data = res.json()["history"]
        st.dataframe(pd.DataFrame(data))
    else:
        st.error("Error")

# ================= BLACKLIST ================= #
elif menu == "Blacklist":

    st.subheader("Blacklist")

    if st.button("Add to Blacklist"):

        requests.post(
            f"{API_URL}/blacklist",
            params={"user_id": user_id, "reason": "manual"},
            headers=headers
        )
        st.success("User blacklisted")

    # 🔥 ADMIN ONLY REMOVE
    if st.session_state.role == "admin":

        if st.button("Remove from Blacklist"):

            res = requests.delete(
                f"{API_URL}/blacklist/{user_id}",
                headers=headers
            )

            if res.status_code == 200:
                st.success("Removed from blacklist")
            else:
                st.error("Failed")

    else:
        st.info("Only admin can remove users")

# ================= LOGOUT ================= #
elif menu == "Logout":
    st.session_state.token = None
    st.session_state.role = None
    st.rerun()