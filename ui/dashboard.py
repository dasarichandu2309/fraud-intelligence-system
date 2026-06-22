import streamlit as st
import requests
import pandas as pd
from jose import jwt, JWTError
import matplotlib.pyplot as plt
import time
import streamlit.components.v1 as components

API_URL = "https://fraud-api-mcgb.onrender.com"

st.set_page_config(page_title="Fraud Intelligence System", layout="wide")

# ================= SESSION ================= #
for key in ["token", "role", "user"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ================= SOUND ================= #
def play_alert_sound():
    components.html(
        """
        <audio autoplay>
        <source src="https://www.soundjay.com/buttons/sounds/beep-07.mp3" type="audio/mpeg">
        </audio>
        """,
        height=0,
    )

# ================= HEADER ================= #
st.markdown("## 🏦 Fraud Intelligence System")
st.caption("Real-time Fraud Detection • Explainable AI • Risk Monitoring")

# ================= LOGIN ================= #
if st.session_state.token is None:

    st.subheader("🔐 Secure Login")

    col1, col2 = st.columns(2)
    username = col1.text_input("Username")
    password = col2.text_input("Password", type="password")

    if st.button("Login", use_container_width=True):

        if not username or not password:
            st.warning("Enter credentials")
        else:
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

                st.success("Login successful")
                st.rerun()
            else:
                st.error("Invalid credentials")

    st.stop()

# ================= AUTH ================= #
headers = {"Authorization": f"Bearer {st.session_state.token}"}

try:
    jwt.decode(st.session_state.token, "supersecretkey", algorithms=["HS256"])
except JWTError:
    st.session_state.clear()
    st.error("Session expired")
    st.rerun()

# ================= SIDEBAR ================= #
st.sidebar.title("⚙️ Control Panel")
st.sidebar.write(f"👤 User: {st.session_state.user}")
st.sidebar.write(f"🔐 Role: {st.session_state.role}")
st.sidebar.success("🟢 System Active")

menu = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Add Transaction", "Predict", "Alerts", "History", "Blacklist", "Logout"]
)

user_id = st.sidebar.number_input("Customer ID", min_value=1, step=1)

# ================= DASHBOARD ================= #
if menu == "Dashboard":

    st.subheader("📊 Live Fraud Monitoring")

    auto_refresh = st.toggle("🔄 Auto Refresh (5 sec)", value=True)

    if auto_refresh:
        time.sleep(5)
        st.rerun()

    res = requests.get(f"{API_URL}/alerts", headers=headers)

    if res.status_code != 200:
        st.error("API Error")
        st.stop()

    alerts = res.json().get("alerts", [])

    if not alerts:
        st.success("🟢 No fraud alerts")
        st.stop()

    df = pd.DataFrame(alerts, columns=["user_id", "amount", "risk", "time"])
    df["time"] = pd.to_datetime(df["time"], errors="coerce")

    # 🚨 HIGH RISK ALERT
    high_risk = df[df["risk"] == "HIGH"]

    if len(high_risk) > 0:
        st.error(f"🚨 {len(high_risk)} HIGH RISK ALERTS!")
        play_alert_sound()

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Alerts", len(df))
    c2.metric("High Risk", len(high_risk))
    c3.metric("Medium Risk", len(df[df["risk"] == "MEDIUM"]))
    c4.metric("Avg Amount", f"{df['amount'].mean():.2f}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("⚠️ Risk Distribution")
        st.bar_chart(df["risk"].value_counts())

    with col2:
        st.subheader("📈 Hourly Trend")
        trend = df.groupby(df["time"].dt.hour)["amount"].count()
        st.line_chart(trend)

    st.divider()

    # Highlight table
    def highlight(row):
        if row["risk"] == "HIGH":
            return ["background-color: red"] * len(row)
        elif row["risk"] == "MEDIUM":
            return ["background-color: orange"] * len(row)
        return [""] * len(row)

    st.subheader("🚨 Live Alerts Feed")
    st.dataframe(df.style.apply(highlight, axis=1), use_container_width=True)

# ================= ADD TRANSACTION ================= #
elif menu == "Add Transaction":

    st.subheader("➕ Add Transaction")

    col1, col2 = st.columns(2)
    amount = col1.number_input("Amount", 0.0)
    hour = col2.slider("Hour", 0, 23)

    if st.button("Add Transaction", use_container_width=True):

        res = requests.post(
            f"{API_URL}/add_transaction",
            json={"user_id": user_id, "amount": amount, "hour": hour},
            headers=headers
        )

        if res.status_code == 200:
            st.success("Transaction added ✅")
        else:
            st.error("Failed")

# ================= PREDICT ================= #
elif menu == "Predict":

    st.subheader("🧠 Fraud Prediction")

    col1, col2 = st.columns(2)
    amount = col1.number_input("Amount", 0.0)
    hour = col2.slider("Hour", 0, 23)

    if st.button("Predict", use_container_width=True):

        with st.spinner("Analyzing..."):

            res = requests.post(
                f"{API_URL}/predict",
                json={"user_id": user_id, "amount": amount, "hour": hour},
                headers=headers
            )

        if res.status_code != 200:
            st.error("Prediction failed")
            st.stop()

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

        # SHAP
        explanation = result.get("explanation", [])
        if explanation:
            st.subheader("📊 Explanation")

            features = [x["feature"] for x in explanation]
            impacts = [x["impact"] for x in explanation]

            fig, ax = plt.subplots()
            ax.barh(features, impacts)
            st.pyplot(fig)

# ================= ALERTS ================= #
elif menu == "Alerts":

    st.subheader("🚨 Alerts")

    res = requests.get(f"{API_URL}/alerts", headers=headers)

    if res.status_code == 200:
        df = pd.DataFrame(res.json()["alerts"], columns=["User", "Amount", "Risk", "Time"])
        st.dataframe(df, use_container_width=True)
    else:
        st.error("Failed")

# ================= HISTORY ================= #
elif menu == "History":

    st.subheader("📜 History")

    res = requests.get(f"{API_URL}/history/{user_id}", headers=headers)

    if res.status_code == 200:
        df = pd.DataFrame(res.json()["history"])
        st.dataframe(df, use_container_width=True)
    else:
        st.error("Error")

# ================= BLACKLIST ================= #
elif menu == "Blacklist":

    if st.session_state.role != "admin":
        st.error("Admin only")
        st.stop()

    st.subheader("🚫 Blacklist")

    col1, col2 = st.columns(2)

    if col1.button("Add User"):
        requests.post(
            f"{API_URL}/blacklist",
            params={"user_id": user_id, "reason": "manual"},
            headers=headers
        )
        st.success("Added")

    if col2.button("Remove User"):
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