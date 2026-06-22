import streamlit as st
import requests
import pandas as pd
from jose import jwt, JWTError
import matplotlib.pyplot as plt
import time
import streamlit.components.v1 as components

API_URL = "https://fraud-api-mcgb.onrender.com"

st.set_page_config(page_title="Fraud Intelligence System", layout="wide")

# ================= GLASS UI ================= #
st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    color: white;
}

.glass {
    background: rgba(255,255,255,0.07);
    backdrop-filter: blur(12px);
    border-radius: 15px;
    padding: 20px;
    border: 1px solid rgba(255,255,255,0.1);
}

.kpi {
    font-size: 26px;
    font-weight: bold;
}
.kpi-title {
    font-size: 14px;
    color: #94a3b8;
}

.stButton>button {
    border-radius: 10px;
    background: linear-gradient(135deg, #6366f1, #22c55e);
    color: white;
}

section[data-testid="stSidebar"] {
    background: rgba(0,0,0,0.5);
}
</style>
""", unsafe_allow_html=True)

# ================= SESSION ================= #
for k in ["token","role","user"]:
    if k not in st.session_state:
        st.session_state[k] = None

# ================= SOUND ================= #
def play_alert():
    components.html("""
    <audio autoplay>
    <source src="https://www.soundjay.com/buttons/sounds/beep-07.mp3">
    </audio>
    """, height=0)

# ================= HEADER ================= #
st.title("🏦 Fraud Intelligence System")
st.caption("Real-time Fraud Detection • Enterprise Dashboard")

# ================= LOGIN ================= #
if st.session_state.token is None:

    st.subheader("🔐 Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        r = requests.post(f"{API_URL}/login", json={"username":u,"password":p})
        if r.status_code==200:
            data = r.json()
            st.session_state.token = data["access_token"]
            decoded = jwt.decode(st.session_state.token,"supersecretkey",algorithms=["HS256"])
            st.session_state.role = decoded["role"]
            st.session_state.user = decoded["sub"]
            st.success("Login success")
            st.rerun()
        else:
            st.error("Invalid credentials")

    st.stop()

# ================= AUTH ================= #
headers = {"Authorization": f"Bearer {st.session_state.token}"}

# ================= SIDEBAR ================= #
st.sidebar.title("⚙️ Control Panel")
st.sidebar.write(f"👤 User: {st.session_state.user}")
st.sidebar.write(f"🔐 Role: {st.session_state.role}")

menu = st.sidebar.radio("Menu",
    ["Dashboard","Predict","Add Transaction","Alerts","History","Logout"])

user_id = st.sidebar.number_input("User ID", min_value=1, step=1)

# ================= AUTO REFRESH ================= #
st.sidebar.markdown("### 🔄 Auto Refresh")
auto = st.sidebar.toggle("Enable", True)
interval = st.sidebar.selectbox("Interval (sec)", [10,30,60,120], index=1)

if auto:
    st.sidebar.info(f"{interval}s refresh")
    time.sleep(interval)
    st.rerun()

# ================= RISK BADGE ================= #
def badge(r):
    c = {"HIGH":"#ef4444","MEDIUM":"#f59e0b","SUSPICIOUS":"#eab308","LOW":"#22c55e"}
    return f"<span style='padding:6px 12px;border-radius:10px;background:{c.get(r)}'>{r}</span>"

# ================= DASHBOARD ================= #
if menu=="Dashboard":

    r = requests.get(f"{API_URL}/alerts", headers=headers)

    if r.status_code!=200:
        st.error("API error")
        st.stop()

    data = r.json().get("alerts",[])

    if not data:
        st.warning("No alerts yet")
        st.stop()

    df = pd.DataFrame(data, columns=["user","amount","risk","time"])

    # ALERT SOUND
    if len(df[df["risk"]=="HIGH"])>0:
        play_alert()

    # KPI
    c1,c2,c3,c4 = st.columns(4)

    def kpi(title,val):
        st.markdown(f"<div class='glass'><div class='kpi-title'>{title}</div><div class='kpi'>{val}</div></div>",unsafe_allow_html=True)

    with c1: kpi("Total",len(df))
    with c2: kpi("High",len(df[df["risk"]=="HIGH"]))
    with c3: kpi("Medium",len(df[df["risk"]=="MEDIUM"]))
    with c4: kpi("Avg",round(df["amount"].mean(),2))

    st.divider()

    col1,col2 = st.columns(2)

    with col1:
        st.markdown("<div class='glass'>",unsafe_allow_html=True)
        st.subheader("Risk Distribution")
        st.bar_chart(df["risk"].value_counts())
        st.markdown("</div>",unsafe_allow_html=True)

    with col2:
        st.markdown("<div class='glass'>",unsafe_allow_html=True)
        df["time"] = pd.to_datetime(df["time"],errors="coerce")
        trend = df.groupby(df["time"].dt.hour)["amount"].count()
        st.line_chart(trend)
        st.markdown("</div>",unsafe_allow_html=True)

    st.markdown("<div class='glass'>",unsafe_allow_html=True)
    st.subheader("🚨 Live Alerts")
    st.dataframe(df, use_container_width=True)
    st.markdown("</div>",unsafe_allow_html=True)

# ================= PREDICT ================= #
elif menu=="Predict":

    st.markdown("<div class='glass'>",unsafe_allow_html=True)

    amt = st.number_input("Amount",0.0)
    hr = st.slider("Hour",0,23)

    if st.button("Predict"):
        r = requests.post(f"{API_URL}/predict",
            json={"user_id":user_id,"amount":amt,"hour":hr},
            headers=headers)

        if r.status_code==200:
            res = r.json()
            prob = max(res["probability"],0.01)
            risk = res["risk"]

            st.markdown(badge(risk),unsafe_allow_html=True)
            st.progress(prob)
            st.metric("Probability",f"{prob*100:.2f}%")

            exp = res.get("explanation",[])
            if exp:
                st.subheader("Why?")
                for e in exp[:3]:
                    st.write(f"{e['feature']} → {round(e['impact'],3)}")

    st.markdown("</div>",unsafe_allow_html=True)

# ================= ADD ================= #
elif menu=="Add Transaction":

    amt = st.number_input("Amount",0.0)
    hr = st.slider("Hour",0,23)

    if st.button("Add"):
        requests.post(f"{API_URL}/add_transaction",
            json={"user_id":user_id,"amount":amt,"hour":hr},
            headers=headers)
        st.success("Added")

# ================= ALERTS ================= #
elif menu=="Alerts":

    r = requests.get(f"{API_URL}/alerts", headers=headers)
    if r.status_code==200:
        df = pd.DataFrame(r.json()["alerts"])
        st.dataframe(df)

# ================= HISTORY ================= #
elif menu=="History":

    r = requests.get(f"{API_URL}/history/{user_id}", headers=headers)
    if r.status_code==200:
        df = pd.DataFrame(r.json()["history"])
        st.dataframe(df)

# ================= LOGOUT ================= #
elif menu=="Logout":
    st.session_state.clear()
    st.rerun()