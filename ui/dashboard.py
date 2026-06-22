import streamlit as st
import requests
import pandas as pd
from jose import jwt, JWTError
import time
import matplotlib.pyplot as plt

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

    st.subheader("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        if not username or not password:
            st.warning("Enter credentials")
        else:
            try:
                res = requests.post(
                    f"{API_URL}/login",
                    json={"username": username, "password": password}
                )

                if res.status_code == 200:
                    data = res.json()

                    st.session_state.token = data["access_token"]

                    decoded = jwt.decode(
                        st.session_state.token,
                        "supersecretkey",
                        algorithms=["HS256"]
                    )

                    st.session_state.role = decoded["role"]
                    st.session_state.user = decoded["sub"]

                    st.success("Login success ✅")
                    st.rerun()

                else:
                    st.error(f"Login failed ❌ ({res.status_code})")
                    st.write(res.text)

            except Exception as e:
                st.error(f"Error: {e}")

    st.stop()

# ================= TOKEN CHECK ================= #
headers = {"Authorization": f"Bearer {st.session_state.token}"}

try:
    jwt.decode(st.session_state.token, "supersecretkey", algorithms=["HS256"])
except JWTError:
    st.session_state.clear()
    st.error("Session expired. Login again.")
    st.rerun()

# ================= SIDEBAR ================= #
st.sidebar.title("Dashboard")
st.sidebar.write(f"👤 User ID: {st.session_state.user}")
st.sidebar.write(f"🔐 Role: {st.session_state.role}")

menu_options = ["Predict", "Alerts", "History"]

if st.session_state.role == "admin":
    menu_options.append("Blacklist")

menu_options.append("Logout")

menu = st.sidebar.selectbox("Menu", menu_options)

# 🔥 Integer input (fixed)
user_id = st.sidebar.number_input("Customer User ID", min_value=1, step=1)

# ================= PREDICT ================= #
if menu == "Predict":

    st.subheader("Fraud Prediction")

    amount = st.number_input("Amount", 0.0)
    hour = st.slider("Hour", 0, 23)

    if st.button("Predict"):

        res = requests.post(
            f"{API_URL}/predict",
            json={
                "user_id": user_id,   # 🔥 integer
                "amount": amount,
                "hour": hour
            },
            headers=headers
        )

        if res.status_code == 200:
            result = res.json()

            prob = result["probability"]
            risk = result["risk"]

            if risk == "HIGH":
                st.error("🔴 HIGH RISK")
            elif risk == "MEDIUM":
                st.warning("🟠 MEDIUM RISK")
            elif risk == "SUSPICIOUS":
                st.info("🟡 SUSPICIOUS")
            else:
                st.success("🟢 SAFE")

            st.progress(prob)
            st.metric("Fraud Probability", f"{prob*100:.2f}%")

            # ================= SHAP ================= #
            explanation = result.get("explanation", [])

            if explanation:
                st.subheader("🧠 Why this prediction?")

                explanation = sorted(explanation, key=lambda x: abs(x["impact"]), reverse=True)

                features = [x["feature"] for x in explanation]
                impacts = [x["impact"] for x in explanation]

                fig, ax = plt.subplots()

                colors = ["red" if x > 0 else "green" for x in impacts]

                ax.barh(features, impacts, color=colors)
                ax.set_xlabel("Impact on Prediction")
                ax.set_title("SHAP Feature Importance")

                st.pyplot(fig)

                # ================= TEXT ================= #
                st.subheader("🔍 Key Reasons")

                for item in explanation[:3]:
                    feature = item["feature"]
                    impact = item["impact"]

                    if impact > 0:
                        st.write(f"🔴 {feature} increased fraud risk")
                    else:
                        st.write(f"🟢 {feature} reduced fraud risk")

        else:
            st.error(f"API Error: {res.status_code}")
            st.write(res.text)

# ================= ALERTS ================= #
elif menu == "Alerts":

    st.subheader("🚨 Live Alerts")

    res = requests.get(f"{API_URL}/alerts", headers=headers)

    if res.status_code == 200:
        alerts = res.json().get("alerts", [])

        if alerts:
            df = pd.DataFrame(alerts, columns=["User", "Amount", "Risk", "Time"])
            st.dataframe(df)
        else:
            st.success("No alerts")

    else:
        st.error(f"Error: {res.status_code}")
        st.write(res.text)

    time.sleep(3)
    st.rerun()

# ================= HISTORY ================= #
elif menu == "History":

    st.subheader("Transaction History")

    res = requests.get(f"{API_URL}/history/{user_id}", headers=headers)

    if res.status_code == 200:
        data = res.json().get("history", [])
        st.dataframe(pd.DataFrame(data))
    else:
        st.error(f"Error: {res.status_code}")
        st.write(res.text)

# ================= BLACKLIST ================= #
elif menu == "Blacklist":

    if st.session_state.role != "admin":
        st.error("Access denied")
        st.stop()

    st.subheader("Blacklist Control")

    if st.button("Add to Blacklist"):
        requests.post(
            f"{API_URL}/blacklist",
            params={"user_id": user_id, "reason": "manual"},
            headers=headers
        )
        st.success("User blacklisted")

    if st.button("Remove from Blacklist"):
        requests.delete(
            f"{API_URL}/blacklist/{user_id}",
            headers=headers
        )
        st.success("Removed from blacklist")

# ================= LOGOUT ================= #
elif menu == "Logout":
    st.session_state.clear()
    st.success("Logged out")
    st.rerun()