import json
import pandas as pd
from datetime import datetime

ALERT_FILE = "/var/ossec/logs/alerts/alerts.json"

def parse_alerts(filepath=ALERT_FILE):
    records = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                alert = json.loads(line)
                records.append(extract_features(alert))
            except json.JSONDecodeError:
                continue
    return pd.DataFrame(records)

def extract_features(alert):
    rule       = alert.get("rule", {})
    agent      = alert.get("agent", {})
    data       = alert.get("data", {})
    timestamp  = alert.get("timestamp", "")

    # Hour of day — attacks often happen in off-hours
    try:
        hour = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).hour
    except:
        hour = 0

    # Source IP — is it internal attacker subnet?
    srcip = data.get("srcip", "")
    is_internal_attacker = 1 if srcip.startswith("192.168.56.3") else 0

    # Rule groups — does it contain auth failure keywords?
    groups = " ".join(rule.get("groups", []))
    is_auth_failure  = 1 if "authentication" in groups else 0
    is_brute_force   = 1 if "brute" in groups.lower() or rule.get("id") in ["5760","100001"] else 0
    is_rootcheck     = 1 if "rootcheck" in groups else 0

    return {
        "rule_id"              : int(rule.get("id", 0)),
        "rule_level"           : int(rule.get("level", 0)),
        "fired_times"          : int(rule.get("firedtimes", 1)),
        "hour_of_day"          : hour,
        "is_internal_attacker" : is_internal_attacker,
        "is_auth_failure"      : is_auth_failure,
        "is_brute_force"       : is_brute_force,
        "is_rootcheck"         : is_rootcheck,
        "agent_id"             : 1 if agent.get("id") == "001" else 0,
        "description"          : rule.get("description", ""),
    }

if __name__ == "__main__":
    df = parse_alerts()
    print(f"Total alerts parsed: {len(df)}")
    print(df[["rule_id","rule_level","is_brute_force","is_auth_failure"]].head(10))
