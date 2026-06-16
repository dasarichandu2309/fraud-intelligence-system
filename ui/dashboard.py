import streamlit as st
import requests
import pandas as pd
from jose import jwt

API_URL = "https://fraud-api-mcgb.onrender.com"

st.set_page_config(layout="wide")

if "token" not in st.session_state:
    st.session_state.token = None

if "role" not in st.session_state:
    st.session_state.role = None

st.title("🏦 Fraud Detection System")

# LOGIN
if st.session_state.token is None:

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        res = requests.post(
            f"{API_URL}/login",
            params={"username": username, "password": password}
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

# DASHBOARD
else:

    headers = {"Authorization": f"Bearer {st.session_state.token}"}

    menu = st.sidebar.selectbox("Menu", ["Predict", "History", "Audit Logs", "Logout"])

    if menu == "Predict":

        user_id = st.number_input("User ID", 1)
        amount = st.number_input("Amount", 0.0)
        hour = st.slider("Hour", 0, 23)

        if st.button("Predict"):

            res = requests.post(
                f"{API_URL}/predict",
                json={
                    "user_id": user_id,
                    "amount": amount,
                    "hour": hour
                },
                headers=headers
            )

            result = res.json()

            if result.get("fraud") == 1:
                st.error("🚨 Fraud Detected")
            else:
                st.success("✅ Safe")

            st.write(f"Risk: {result.get('risk')}")

            if "explanation" in result:
                df = pd.DataFrame(result["explanation"].items(), columns=["Feature", "Impact"])
                st.bar_chart(df.set_index("Feature"))

    elif menu == "History":

        user_id = st.number_input("User ID", 1)

        if st.button("Fetch"):
            res = requests.get(f"{API_URL}/history/{user_id}", headers=headers)
            data = res.json().get("history", [])
            st.dataframe(pd.DataFrame(data))

    elif menu == "Audit Logs":

        res = requests.get(f"{API_URL}/audit_logs", headers=headers)
        logs = res.json().get("logs", [])
        st.dataframe(pd.DataFrame(logs))

    elif menu == "Logout":
        st.session_state.token = None
        st.session_state.role = None
        st.rerun()