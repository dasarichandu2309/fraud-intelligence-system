import streamlit as st
import requests
import pandas as pd

# =========================
# 🔥 PAGE CONFIG
# =========================
st.set_page_config(page_title="Fraud Intelligence System", layout="wide")

st.title("💳 Real-Time Fraud Intelligence System")
st.markdown("Advanced Fraud Detection with Behavior Analysis & Explainability")

# =========================
# 🔹 INPUT SECTION
# =========================
st.sidebar.header("🔹 Transaction Input")

user_id = st.sidebar.number_input("User ID", min_value=1, value=1)
amount = st.sidebar.number_input("Amount", min_value=0.0, value=100.0)
hour = st.sidebar.slider("Hour", 0, 23, 12)

# =========================
# 🔥 BUTTON
# =========================
if st.sidebar.button("🚀 Analyze Transaction"):

    data = {
        "user_id": user_id,
        "Amount": amount,
        "hour": hour
    }

    try:
        response = requests.post("https://fraud-api-mcgb.onrender.com/predict", json=data)

        if response.status_code != 200:
            st.error("❌ API Error")
            st.write(response.text)
            st.stop()

        result = response.json()

        # =========================
        # 🔥 FINAL DECISION
        # =========================
        st.subheader("📊 Final Decision")

        if result["final_prediction"] == 1:
            st.error(result["final_meaning"])
        else:
            st.success(result["final_meaning"])

        # =========================
        # 🔥 SUMMARY
        # =========================
        st.markdown("### 🧾 Summary")
        st.info(f"""
User **{user_id}** made a transaction of **₹{amount}** at hour **{hour}**.

System analyzed:
- Behavior patterns
- Transaction velocity
- Statistical deviation
- ML + anomaly detection

Final verdict: **{result['final_meaning']}**
""")

        # =========================
        # 🔥 METRICS
        # =========================
        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Fraud Model", result["fraud_meaning"])
        col2.metric("Anomaly", result["anomaly_meaning"])
        col3.metric("Risk Score", result["risk_score"])
        col4.metric("Velocity", result["velocity"])

        # =========================
        # 🔥 USER BEHAVIOR
        # =========================
        st.markdown("### 🧠 User Behavior Insights")

        col1, col2 = st.columns(2)

        col1.write(f"🆔 User ID: {user_id}")
        col1.write(f"💸 Transaction Amount: {amount}")
        col1.write(f"⏰ Hour: {hour}")

        col2.write(f"⚡ Velocity (last 60 sec): {result['velocity']}")
        col2.write(f"🕒 Time Difference: {round(result['time_difference'], 2)}")

        # =========================
        # 📈 TRANSACTION TREND
        # =========================
        st.markdown("### 📈 Transaction Trend")

        if "history" not in st.session_state:
            st.session_state.history = []

        st.session_state.history.append(amount)

        hist_df = pd.DataFrame({
            "Transaction": range(len(st.session_state.history)),
            "Amount": st.session_state.history
        })

        st.line_chart(hist_df.set_index("Transaction"))

        # =========================
        # 🧾 RECENT TRANSACTIONS
        # =========================
        st.markdown("### 🧾 Recent Transactions")

        table_df = pd.DataFrame({
            "Amount": st.session_state.history
        })

        st.dataframe(table_df.tail(5))

        # =========================
        # 🚨 FRAUD REASONS
        # =========================
        st.markdown("### 🚨 Fraud Reasons")

        if len(result["reasons"]) > 0:
            for reason in result["reasons"]:
                st.warning(f"⚠️ {reason}")
        else:
            st.success("No strong fraud signals detected")

        # =========================
        # 🚨 SMART ALERT
        # =========================
        st.markdown("### 🚨 Smart Alerts")

        if result["risk_score"] >= 3:
            st.error("🚨 HIGH RISK: Immediate action required!")
        elif result["risk_score"] == 2:
            st.warning("⚠️ Medium Risk: Monitor closely")
        else:
            st.success("✅ Low Risk: Normal activity")

        # =========================
        # 🧠 SHAP ANALYSIS
        # =========================
        st.markdown("### 🧠 Feature Impact Analysis")

        shap_vals = result["shap_values"]

        clean = {}
        for k, v in shap_vals.items():
            try:
                clean[k] = float(v)
            except:
                continue

        if len(clean) > 0:
            df = pd.DataFrame({
                "Feature": list(clean.keys()),
                "Impact": list(clean.values())
            })

            df = df.sort_values(by="Impact", key=abs, ascending=False)

            st.bar_chart(df.set_index("Feature"))

        else:
            st.warning("SHAP not available")

    except Exception as e:
        st.error(f"❌ ERROR: {e}")