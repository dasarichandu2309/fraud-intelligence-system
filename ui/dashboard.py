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
                    st.error("Login failed ❌")

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
st.sidebar.success("🟢 System Active")

menu = st.sidebar.selectbox(
    "Menu",
    ["Dashboard", "Predict", "Alerts", "History", "Blacklist", "Logout"]
)

# integer input
user_id = st.sidebar.number_input("Customer User ID", min_value=1, step=1)

# ================= DASHBOARD ================= #
if menu == "Dashboard":

    st.title("📊 Fraud Intelligence Dashboard")

    res = requests.get(f"{API_URL}/alerts", headers=headers)

    if res.status_code != 200:
        st.error("Failed to fetch data")
        st.stop()

    alerts = res.json().get("alerts", [])

    if not alerts:
        st.warning("No data available")
        st.stop()

    df = pd.DataFrame(alerts, columns=["user_id", "amount", "risk", "time"])
    df["time"] = pd.to_datetime(df["time"], errors="coerce")

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Alerts", len(df))
    col2.metric("High Risk", len(df[df["risk"] == "HIGH"]))
    col3.metric("Medium Risk", len(df[df["risk"] == "MEDIUM"]))
    col4.metric("Avg Amount", f"{df['amount'].mean():.2f}")

    st.divider()

    # Risk distribution
    st.subheader("⚠️ Risk Distribution")
    st.bar_chart(df["risk"].value_counts())

    st.divider()

    # Trend
    st.subheader("📈 Fraud Trend (Hourly)")
    trend = df.groupby(df["time"].dt.hour)["amount"].count()
    st.line_chart(trend)

    st.divider()

    # Top users
    st.subheader("👤 Top Risky Users")
    top_users = df.groupby("user_id")["amount"].count().sort_values(ascending=False).head(10)
    st.bar_chart(top_users)

    st.divider()

    # High risk
    st.subheader("🔴 High Risk Transactions")
    st.dataframe(df[df["risk"] == "HIGH"])

    st.divider()

    # Styled table
    def highlight(val):
        if val == "HIGH":
            return "background-color: red"
        elif val == "MEDIUM":
            return "background-color: orange"
        return ""

    st.subheader("🚨 Live Alerts")
    st.dataframe(df.style.applymap(highlight, subset=["risk"]))

# ================= PREDICT ================= #
elif menu == "Predict":

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

            prob = result["probability"]
            risk = result["risk"]
            is_anomaly = result["anomaly"]

            # Risk display
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

            # SHAP
            explanation = result.get("explanation", [])

            if explanation:
                st.subheader("🧠 Why this prediction?")

                explanation = sorted(explanation, key=lambda x: abs(x["impact"]), reverse=True)

                features = [x["feature"] for x in explanation]
                impacts = [x["impact"] for x in explanation]

                fig, ax = plt.subplots()
                colors = ["red" if x > 0 else "green" for x in impacts]

                ax.barh(features, impacts, color=colors)
                ax.set_title("SHAP Feature Importance")

                st.pyplot(fig)

                st.subheader("🔍 Key Reasons")

                for item in explanation[:3]:
                    if item["impact"] > 0:
                        st.write(f"🔴 {item['feature']} increased fraud risk")
                    else:
                        st.write(f"🟢 {item['feature']} reduced fraud risk")

            # Business insight
            st.subheader("🧠 Risk Insight")

            if prob > 0.8:
                st.error("Highly likely fraud. Immediate action required.")
            elif prob > 0.5:
                st.warning("Suspicious transaction. Monitor.")
            elif is_anomaly:
                st.info("Unusual behavior detected.")
            else:
                st.success("Normal transaction.")

        else:
            st.error("API Error")

# ================= ALERTS ================= #
elif menu == "Alerts":

    st.subheader("🚨 Live Alerts")

    res = requests.get(f"{API_URL}/alerts", headers=headers)

    if res.status_code == 200:
        alerts = res.json().get("alerts", [])

        df = pd.DataFrame(alerts, columns=["User", "Amount", "Risk", "Time"])

        def highlight(val):
            if val == "HIGH":
                return "background-color: red"
            elif val == "MEDIUM":
                return "background-color: orange"
            return ""

        st.dataframe(df.style.applymap(highlight, subset=["Risk"]))

    else:
        st.error("Error fetching alerts")

# ================= HISTORY ================= #
elif menu == "History":

    st.subheader("Transaction History")

    res = requests.get(f"{API_URL}/history/{user_id}", headers=headers)

    if res.status_code == 200:
        data = res.json().get("history", [])
        st.dataframe(pd.DataFrame(data))
    else:
        st.error("Error fetching history")

# ================= BLACKLIST ================= #
elif menu == "Blacklist":

    if st.session_state.role != "admin":
        st.error("Admin only")
        st.stop()

    st.subheader("Blacklist Control")

    if st.button("Add"):
        requests.post(
            f"{API_URL}/blacklist",
            params={"user_id": user_id, "reason": "manual"},
            headers=headers
        )
        st.success("Added")

    if st.button("Remove"):
        requests.delete(
            f"{API_URL}/blacklist/{user_id}",
            headers=headers
        )
        st.success("Removed")

# ================= LOGOUT ================= #
elif menu == "Logout":
    st.session_state.clear()
    st.success("Logged out")
    st.rerun()