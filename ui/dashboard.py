import streamlit as st
import requests
import pandas as pd
from jose import jwt
import time

API_URL = "https://fraud-api-mcgb.onrender.com"

st.set_page_config(page_title="Fraud Intelligence System", layout="wide")

# ================= UI STYLE ================= #
st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    color: white;
}
.stButton>button {
    border-radius: 10px;
    background: linear-gradient(135deg,#6366f1,#22c55e);
    color: white;
}
</style>
""", unsafe_allow_html=True)

# ================= SESSION ================= #
for k in ["token","role","user"]:
    if k not in st.session_state:
        st.session_state[k] = None

# ================= LOGIN ================= #
if st.session_state.token is None:
    st.title("🔐 Login")

    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        r = requests.post(f"{API_URL}/login", json={"username":u,"password":p})
        if r.status_code == 200:
            data = r.json()
            st.session_state.token = data["access_token"]

            decoded = jwt.decode(data["access_token"], "supersecretkey", algorithms=["HS256"])
            st.session_state.role = decoded["role"]
            st.session_state.user = decoded["sub"]

            st.success("Login success")
            st.rerun()
        else:
            st.error("Invalid credentials")

    st.stop()

headers = {"Authorization": f"Bearer {st.session_state.token}"}

# ================= SIDEBAR ================= #
st.sidebar.title("⚙️ Control Panel")
st.sidebar.write(f"👤 User: {st.session_state.user}")
st.sidebar.write(f"🔐 Role: {st.session_state.role}")

menu = st.sidebar.radio(
    "Menu",
    ["Dashboard","Predict","Add Transaction","Alerts","History","Blacklist","Audit Logs","Logout"]
)

user_id = st.sidebar.number_input("User ID", min_value=1, step=1)

# ================= AUTO REFRESH ================= #
auto = st.sidebar.toggle("Auto Refresh", True)
interval = st.sidebar.selectbox("Interval (sec)", [10,30,60], index=1)

if auto:
    time.sleep(interval)
    st.rerun()

# ================= RISK FORMAT ================= #
def risk_color(r):
    return {
        "HIGH": "🔴 HIGH",
        "MEDIUM": "🟠 MEDIUM",
        "SUSPICIOUS": "🟡 SUSPICIOUS",
        "LOW": "🟢 LOW"
    }.get(r, r)

# ================= DASHBOARD ================= #
if menu == "Dashboard":

    st.title("📊 Fraud Dashboard")

    r = requests.get(f"{API_URL}/alerts", headers=headers)

    data = r.json().get("alerts", []) if r.status_code == 200 else []

    if not data:
        r = requests.get(f"{API_URL}/history/{user_id}", headers=headers)
        data = r.json().get("history", []) if r.status_code == 200 else []

    if not data:
        st.warning("No data available")
        st.stop()

    df = pd.DataFrame(data)

    if "user_id" not in df.columns:
        df.columns = ["user_id","amount","risk","time"]

    df["time"] = pd.to_datetime(df["time"], errors="coerce")

    # ================= KPIs ================= #
    c1,c2,c3,c4 = st.columns(4)

    c1.metric("Transactions", len(df))
    c2.metric("High Risk", (df["risk"]=="HIGH").sum())
    c3.metric("Medium Risk", (df["risk"]=="MEDIUM").sum())
    c4.metric("Avg Amount", round(df["amount"].mean(),2))

    st.divider()

    # ================= CHARTS ================= #
    col1,col2 = st.columns(2)

    with col1:
        st.subheader("Risk Distribution")
        st.bar_chart(df["risk"].value_counts())

    with col2:
        st.subheader("Hourly Trend")
        trend = df.groupby(df["time"].dt.hour)["amount"].count()
        st.line_chart(trend)

    st.subheader("Amount by Risk")
    st.bar_chart(df.groupby("risk")["amount"].mean())

    st.divider()

    df["risk"] = df["risk"].apply(risk_color)
    st.dataframe(df, use_container_width=True)

# ================= PREDICT ================= #
elif menu == "Predict":

    st.title("🔮 Fraud Prediction")

    amt = st.number_input("Amount",0.0)
    hr = st.slider("Hour",0,23)

    if st.button("Predict"):

        r = requests.post(
            f"{API_URL}/predict",
            json={
                "user_id":user_id,
                "amount":amt,
                "hour":hr,
                "device_id":"web_app",
                "location":"IN"
            },
            headers=headers
        )

        if r.status_code == 200:

            res = r.json()
            prob = res["probability"]
            risk = res["risk"]

            st.success(risk_color(risk))
            st.progress(prob)
            st.metric("Fraud Probability", f"{prob*100:.2f}%")

            # ================= REASONS ================= #
            if "reasons" in res:
                st.subheader("🧠 Risk Reasons")
                for reason in res["reasons"]:
                    st.write(f"⚠️ {reason}")

            # ================= SHAP ================= #
            exp = res.get("explanation",[])
            if exp:
                st.subheader("📊 Feature Impact")
                for e in exp[:5]:
                    st.write(f"{e['feature']} → {round(e['impact'],3)}")

# ================= ADD ================= #
elif menu == "Add Transaction":

    st.title("➕ Add Transaction")

    amt = st.number_input("Amount",0.0)
    hr = st.slider("Hour",0,23)

    if st.button("Add"):
        r = requests.post(
            f"{API_URL}/add_transaction",
            json={"user_id":user_id,"amount":amt,"hour":hr},
            headers=headers
        )

        if r.status_code == 200:
            st.success("Transaction Added")
        else:
            st.error("Failed")

# ================= ALERTS ================= #
elif menu == "Alerts":

    st.title("🚨 Alerts")

    r = requests.get(f"{API_URL}/alerts", headers=headers)
    if r.status_code == 200:
        df = pd.DataFrame(r.json()["alerts"])
        df["risk"] = df["risk"].apply(risk_color)
        st.dataframe(df)

# ================= HISTORY ================= #
elif menu == "History":

    st.title("📜 History")

    r = requests.get(f"{API_URL}/history/{user_id}", headers=headers)
    if r.status_code == 200:
        df = pd.DataFrame(r.json()["history"])
        st.dataframe(df)

# ================= BLACKLIST ================= #
elif menu == "Blacklist":

    if st.session_state.role != "admin":
        st.error("Admin only")
        st.stop()

    st.title("🚫 Blacklist Management")

    col1,col2 = st.columns(2)

    if col1.button("➕ Add User"):
        r = requests.post(
            f"{API_URL}/blacklist",
            params={"user_id":user_id,"reason":"manual"},
            headers=headers
        )
        st.success("Added" if r.status_code==200 else "Failed")

    if col2.button("❌ Remove User"):
        r = requests.delete(
            f"{API_URL}/blacklist/{user_id}",
            headers=headers
        )
        st.success("Removed" if r.status_code==200 else "Failed")

    # SHOW HIGH RISK USERS
    st.subheader("⚠️ Blacklisted Users")

    r = requests.get(f"{API_URL}/audit_logs", headers=headers)

    if r.status_code == 200:
        df = pd.DataFrame(r.json()["logs"], columns=["user_id","amount","risk","time"])
        df = df[df["risk"]=="HIGH"]

        if df.empty:
            st.info("No blacklisted users")
        else:
            st.dataframe(df)

# ================= AUDIT ================= #
elif menu == "Audit Logs":

    if st.session_state.role != "admin":
        st.error("Admin only")
        st.stop()

    st.title("📜 Audit Logs")

    r = requests.get(f"{API_URL}/audit_logs", headers=headers)

    if r.status_code == 200:
        df = pd.DataFrame(r.json()["logs"], columns=["user_id","amount","risk","time"])
        st.dataframe(df)

# ================= LOGOUT ================= #
elif menu == "Logout":
    st.session_state.clear()
    st.rerun()