import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import MinMaxScaler
import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from features import parse_alerts

FEATURES = [
    "rule_level", "fired_times", "hour_of_day",
    "is_internal_attacker", "is_auth_failure",
    "is_brute_force", "is_rootcheck", "agent_id"
]

def assign_label(row):
    """Rule-based labeling for training — higher = more critical"""
    if row["is_brute_force"] == 1:
        return 2   # HIGH
    elif row["is_auth_failure"] == 1 and row["rule_level"] >= 10:
        return 2   # HIGH
    elif row["rule_level"] >= 10:
        return 2   # HIGH
    elif row["rule_level"] >= 7:
        return 1   # MEDIUM
    else:
        return 0   # LOW

def risk_score(probability_vector):
    """Convert class probabilities to 0-100 risk score"""
    # LOW=0, MEDIUM=1, HIGH=2
    weights = np.array([0, 50, 100])
    return round(float(np.dot(probability_vector, weights)), 2)

def train_model(df):
    df["label"] = df.apply(assign_label, axis=1)
    X = df[FEATURES].fillna(0)
    y = df["label"]

    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X)

    model = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
        class_weight="balanced"
    )
    model.fit(X_scaled, y)
    return model, scaler

def score_alerts(df, model, scaler):
    X = df[FEATURES].fillna(0)
    X_scaled = scaler.transform(X)
    proba = model.predict_proba(X_scaled)

    # Pad probabilities if only 2 classes present
    n_classes = proba.shape[1]
    if n_classes == 2:
        proba = np.hstack([proba, np.zeros((len(proba), 1))])

    df = df.copy()
    df["risk_score"] = [risk_score(p) for p in proba]
    df["risk_label"] = df["risk_score"].apply(
        lambda s: "HIGH" if s >= 70 else ("MEDIUM" if s >= 30 else "LOW")
    )
    return df

if __name__ == "__main__":
    print("[*] Loading alerts...")
    df = parse_alerts()

    print("[*] Training Random Forest model...")
    model, scaler = train_model(df)

    print("[*] Scoring all alerts...")
    results = score_alerts(df, model, scaler)

    print("\n=== RISK SCORE SUMMARY ===")
    print(results["risk_label"].value_counts())

    print("\n=== TOP HIGH RISK ALERTS ===")
    high = results[results["risk_label"] == "HIGH"][
        ["rule_id", "rule_level", "is_brute_force",
         "is_auth_failure", "risk_score", "description"]
    ].sort_values("risk_score", ascending=False).head(10)
    print(high.to_string(index=False))

    print("\n=== FEATURE IMPORTANCE ===")
    for feat, imp in sorted(
        zip(FEATURES, model.feature_importances_),
        key=lambda x: x[1], reverse=True
    ):
        print(f"  {feat:<25} {imp:.4f}")
