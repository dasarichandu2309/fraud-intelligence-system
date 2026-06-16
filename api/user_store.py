import pandas as pd
import time

# 🔥 In-memory DB
user_data = {}

def update_user(user_id, amount, hour):

    current_time = time.time()

    if user_id not in user_data:
        user_data[user_id] = []

    # store full transaction
    user_data[user_id].append({
        "amount": amount,
        "time": current_time,
        "hour": hour
    })

    history = user_data[user_id]

    df = pd.DataFrame(history)

    # ------------------------
    # BASIC FEATURES
    # ------------------------
    avg = df["amount"].mean()
    std = df["amount"].std() if len(df) > 1 else 0
    count = len(df)

    # ------------------------
    # 🔥 VELOCITY FEATURE
    # ------------------------
    last_60_sec = df[df["time"] > current_time - 60]
    velocity = len(last_60_sec)

    # ------------------------
    # 🔥 TIME ANOMALY
    # ------------------------
    avg_hour = df["hour"].mean()
    time_diff = abs(hour - avg_hour)

    # ------------------------
    # 🔥 SPIKE DETECTION
    # ------------------------
    deviation = amount - avg

    return {
        "avg": avg,
        "std": std,
        "count": count,
        "velocity": velocity,
        "time_diff": time_diff,
        "deviation": deviation
    }