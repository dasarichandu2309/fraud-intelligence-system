import streamlit as st
import requests
import pandas as pd
from jose import jwt

API_URL = "https://fraud-api-mcgb.onrender.com"

st.set_page_config(layout="wide")

# SESSION
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

headers = {"Authorization": f"Bearer {st.session_state.token}"}

st.sidebar.write(f"Role: {st.session_state.role}")
user_id = st.sidebar.text_input("Customer User ID", "user1")

menu = st.sidebar.selectbox(
    "Menu",
    ["Dashboard", "Predict", "History", "Blacklist", "Logout"]
)

# ================= DASHBOARD ================= #
if menu == "Dashboard":

    st.subheader("📊 Analytics Dashboard")

    res = requests.get(f"{API_URL}/stats", headers=headers)
    data = res.json()

    col1, col2, col3 = st.columns(3)

    col1.metric("Total Transactions", data["total"])
    col2.metric("Fraud Cases", data["fraud"])
    col3.metric("Safe Transactions", data["safe"])

    # PIE CHART
    st.subheader("Fraud vs Safe")
    pie_df = pd.DataFrame({
        "Type": ["Fraud", "Safe"],
        "Count": [data["fraud"], data["safe"]]
    })
    st.bar_chart(pie_df.set_index("Type"))

    # TREND CHART
    st.subheader("Transactions Over Time")
    trend_df = pd.DataFrame(data["trend"], columns=["Date", "Count"])
    st.line_chart(trend_df.set_index("Date"))

    # FRAUD USERS
    st.subheader("Fraud by Users")
    user_df = pd.DataFrame(data["fraud_users"], columns=["User", "Fraud Count"])
    st.bar_chart(user_df.set_index("User"))

# ================= PREDICT ================= #
elif menu == "Predict":

    amount = st.number_input("Amount", 0.0)
    hour = st.slider("Hour", 0, 23)

    if st.button("Predict"):

        res = requests.post(
            f"{API_URL}/predict",
            json={"user_id": user_id, "amount": amount, "hour": hour},
            headers=headers
        )

        result = res.json()

        if result["fraud"]:
            st.error("🚨 Fraud Detected")
        else:
            st.success("✅ Safe")

        st.write("Risk:", result["risk"])

# ================= HISTORY ================= #
elif menu == "History":

    res = requests.get(f"{API_URL}/history/{user_id}", headers=headers)
    st.dataframe(pd.DataFrame(res.json()["history"]))

# ================= BLACKLIST ================= #
elif menu == "Blacklist":

    if st.button("Add to Blacklist"):
        requests.post(
            f"{API_URL}/blacklist",
            params={"user_id": user_id, "reason": "manual"},
            headers=headers
        )
        st.success("Blacklisted")

    if st.session_state.role == "admin":
        if st.button("Remove"):
            requests.delete(f"{API_URL}/blacklist/{user_id}", headers=headers)
            st.success("Removed")

# ================= LOGOUT ================= #
elif menu == "Logout":
    st.session_state.token = None
    st.rerun()