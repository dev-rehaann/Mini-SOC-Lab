# SOC Lab Field Manual
### Build a Production-Grade Mini Security Operations Center from Scratch

**Version:** 1.0 | **Tested On:** VirtualBox · Ubuntu Server 24.04 LTS · Wazuh 4.14
**Difficulty:** Intermediate | **Time:** 4–6 hours

---

## What You Will Build

A 3-VM SOC lab that detects attacks in real time, fires custom MITRE-mapped rules, auto-blocks attackers via iptables, and scores every alert 0–100 with ML.

```
ATTACKER VM (192.168.56.30)
      │  SSH Brute Force (Hydra)
      ▼
VICTIM VM (192.168.56.20)
   Apache2 + SSH + Wazuh Agent
      │  Log forwarding
      ▼
SOC SERVER VM (192.168.56.10)
   Wazuh Manager + Indexer + Dashboard + Filebeat + ML Scoring
      │
      ▼
https://192.168.56.10  (Wazuh Dashboard)
```

---

## Downloads — Get Everything First

| Tool | Link | Notes |
|---|---|---|
| Oracle VirtualBox | https://www.virtualbox.org/wiki/Downloads | Host hypervisor |
| VirtualBox Extension Pack | https://www.virtualbox.org/wiki/Downloads | Same page, match VirtualBox version |
| Ubuntu Server 24.04 LTS | https://ubuntu.com/download/server | SOC Server + Victim VMs |
| Ubuntu Desktop 26.04 | https://ubuntu.com/download/desktop | Attacker VM |
| Wazuh Docs | https://documentation.wazuh.com/current/index.html | Full reference |
| Wazuh Install Script | https://packages.wazuh.com/4.14/wazuh-install.sh | Downloaded during install |
| Wazuh Alert Template | https://raw.githubusercontent.com/wazuh/wazuh/v4.14.5/extensions/elasticsearch/7.x/wazuh-template.json | Emergency fix only |
| Hydra | https://github.com/vanhauser-thc/thc-hydra | Installed via apt |
| scikit-learn | https://scikit-learn.org/stable/ | ML library |
| MITRE T1110 | https://attack.mitre.org/techniques/T1110/ | Brute Force |
| MITRE T1078 | https://attack.mitre.org/techniques/T1078/ | Valid Accounts |

---

## Host Machine Requirements

| Item | Minimum | This Build Used |
|---|---|---|
| RAM | 16 GB | 32 GB |
| Free Disk | 50 GB | 80 GB |
| CPU | 4 cores | 6+ recommended |

---

## VM Specs

| VM | OS | RAM | CPU | Disk | IP |
|---|---|---|---|---|---|
| SOC Server | Ubuntu Server 24.04 LTS | 6 GB | 2 | 25 GB | 192.168.56.10 |
| Victim | Ubuntu Server 24.04 LTS | 2 GB | 1 | 10 GB | 192.168.56.20 |
| Attacker | Ubuntu Desktop 26.04 | 4 GB | 2 | 15 GB | 192.168.56.30 |

---

## Phase 1 — VirtualBox Host Setup

### Create the Host-Only Network

1. VirtualBox → File → Tools → Network Manager
2. Click Create → `vboxnet0` appears
3. Properties → DHCP Server tab → uncheck Enable Server → Save

> DHCP must be OFF. Static IPs only — DHCP causes conflicts.

---

## Phase 2 — SOC Server VM

### Create VM

Machine → New:
- Name: SOC-Server | Type: Linux | Version: Ubuntu 24.04 LTS (64-bit)
- RAM: 6144 MB | CPU: 2 | Disk: 25 GB dynamic VDI

> **Disk Warning:** Set to 50 GB if possible. Wazuh needs ~10 GB. A 25 GB disk with default LVM
> leaves only ~12 GB usable. If install fails with "No space left on device", see Troubleshooting.

Settings → Network:
- Adapter 1: NAT
- Adapter 2: Host-only Adapter → vboxnet0

### Install Ubuntu Server

Boot with ubuntu-24.04-live-server-amd64.iso. During install:

Network config screen — enp0s8 (Host-only adapter):
- IPv4: Manual
- Subnet: 192.168.56.0/24
- Address: 192.168.56.10
- Gateway: blank
- DNS: 8.8.8.8

Profile: username zaig, hostname soc-server. Enable OpenSSH.

> If "Network connection failed" popup appears — not fatal. Continue without network.

### Verify Network

```bash
ip a
# enp0s3: 10.0.2.x (NAT) + enp0s8: 192.168.56.10/24 (Host-only)

ping -c 3 google.com
```

If enp0s8 shows wrong subnet or is missing:

```bash
sudo nano /etc/netplan/00-installer-config.yaml
```

```yaml
network:
  ethernets:
    enp0s3:
      dhcp4: true
    enp0s8:
      addresses:
        - 192.168.56.10/24
      nameservers:
        addresses: [8.8.8.8]
  version: 2
```

```bash
sudo netplan apply
```

> netplan YAML: spaces only (no tabs). Key is addresses: (plural) not address:.
> On Ubuntu Desktop: add renderer: NetworkManager under network:.

```bash
sudo apt update && sudo apt upgrade -y
```

SSH in from host: `ssh zaig@192.168.56.10`

---

## Phase 3 — Wazuh Installation

### Check Disk First

```bash
df -h /
# Need 12 GB free minimum
```

### Install

```bash
curl -sO https://packages.wazuh.com/4.14/wazuh-install.sh
sudo bash ./wazuh-install.sh -a
```

Installs: Manager + Indexer (OpenSearch) + Dashboard + Filebeat. Takes 15-25 min.

At end: `The password for user admin is: <SAVE THIS>`

### Verify Services

```bash
sudo systemctl status wazuh-manager wazuh-indexer wazuh-dashboard filebeat --no-pager -l
```

All four: active (running)

> **Known Issue 1 — Indexer AccessDeniedException:**
> ```
> java.nio.file.AccessDeniedException: /etc/wazuh-indexer/backup
> ```
> Fix:
> ```bash
> sudo chown -R wazuh-indexer:wazuh-indexer /etc/wazuh-indexer/
> sudo systemctl restart wazuh-indexer
> ```

> **Known Issue 2 — Dashboard missing SSL cert:**
> ```
> ENOENT: /etc/wazuh-dashboard/certs/dashboard-key.pem
> ```
> Fix:
> ```bash
> sudo mkdir -p /etc/wazuh-dashboard/certs
> sudo cp /home/zaig/wazuh-certificates/dashboard.pem /etc/wazuh-dashboard/certs/
> sudo cp /home/zaig/wazuh-certificates/dashboard-key.pem /etc/wazuh-dashboard/certs/
> sudo cp /home/zaig/wazuh-certificates/root-ca.pem /etc/wazuh-dashboard/certs/
> sudo chown -R wazuh-dashboard:wazuh-dashboard /etc/wazuh-dashboard/certs
> sudo find /etc/wazuh-dashboard/certs -type f -exec chmod 400 {} \;
> sudo systemctl restart wazuh-dashboard
> ```

### Access Dashboard

Browser: https://192.168.56.10 | Username: admin | Password: from install

Accept SSL warning (self-signed cert). The wazuh-alerts-* warning on home page is normal — resolves after first agent connects.

Snapshot now: `Wazuh-Ready-Clean`

---

## Phase 4 — Victim VM

### Create VM

- Name: Victim | RAM: 2048 MB | CPU: 1 | Disk: 10 GB dynamic
- Adapters: NAT + Host-only (vboxnet0)
- ISO: ubuntu-24.04-live-server-amd64.iso

Network on enp0s8: Address 192.168.56.20/24 | Hostname: zaig-VirtualBox | OpenSSH: enabled

### Fix Network If Needed

Same netplan fix as SOC Server — IP: 192.168.56.20/24.

```bash
ping -c 3 192.168.56.10   # must succeed
```

### Install Services and Fake Users

```bash
sudo apt update && sudo apt install -y apache2 openssh-server curl

sudo useradd -m -s /bin/bash testuser
sudo useradd -m -s /bin/bash adminuser
echo "testuser:S3cur3T3st@2024" | sudo chpasswd
echo "adminuser:Adm1n@S3cur3#99" | sudo chpasswd
```

> BAD PASSWORD warning from chpasswd = warning only, not error. Use mixed passwords above.

```bash
id testuser && id adminuser
sudo systemctl status apache2 ssh --no-pager | grep Active
curl -I http://192.168.56.20    # expect HTTP/1.1 200 OK
```

### Install Wazuh Agent

```bash
curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | sudo gpg \
  --no-default-keyring --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg \
  --import && sudo chmod 644 /usr/share/keyrings/wazuh.gpg

echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" \
  | sudo tee /etc/apt/sources.list.d/wazuh.list

sudo apt update && WAZUH_MANAGER="192.168.56.10" sudo apt install -y wazuh-agent

sudo systemctl daemon-reload
sudo systemctl enable wazuh-agent
sudo systemctl start wazuh-agent
```

### Verify Connection

On SOC Server:

```bash
sudo /var/ossec/bin/agent_control -l
```

Expected:
```
ID: 000, Name: soc-server, IP: 127.0.0.1, Active/Local
ID: 001, Name: zaig-VirtualBox, IP: any, Active
```

Active = logs are flowing.

Snapshot: `Agent-Connected-Clean`

---

## Phase 5 — Attacker VM

### Create VM

- Name: Attacker | RAM: 4096 MB | CPU: 2 | Disk: 15 GB dynamic
- Adapters: NAT + Host-only (vboxnet0)
- ISO: ubuntu-26.04-desktop-amd64.iso
- Version in dropdown: Ubuntu 24.04 LTS (26.04 not listed, fine)

### Set Static IP After Install

```bash
sudo nano /etc/netplan/01-network-manager-all.yaml
```

```yaml
network:
  ethernets:
    enp0s3:
      dhcp4: true
    enp0s8:
      addresses:
        - 192.168.56.30/24
      nameservers:
        addresses: [8.8.8.8]
  version: 2
```

```bash
sudo netplan apply
ping -c 3 192.168.56.10
ping -c 3 192.168.56.20
```

### Install Tools

```bash
sudo apt update && sudo apt install -y hydra nmap
```

Snapshot: `Attacker-Clean`

---

## Phase 6 — Attack Simulation

> Snapshot all VMs before this phase.

Open dashboard: https://192.168.56.10 → Threat Hunting → Events → Last 24 hours

### Create Wordlist (Attacker VM)

```bash
cat << 'EOF' > ~/passwords.txt
password
123456
admin
Password123
S3cur3T3st@2024
test123
letmein
welcome
EOF
```

### Run SSH Brute Force

```bash
hydra -l testuser -P ~/passwords.txt 192.168.56.20 ssh -t 4 -V
```

Output will show: `[22][ssh] host: 192.168.56.20  login: testuser  password: S3cur3T3st@2024`

### Verify Alerts

Dashboard search: `rule.id: 5760`

You should see SSH authentication failure events from 192.168.56.30.

> **Known Issue — Dashboard shows no results despite attack happening:**
>
> Root cause: wazuh-alerts-* index does not exist in Indexer. Filebeat not shipping data.
>
> Diagnose:
> ```bash
> curl -k -u admin:<PASSWORD> "https://127.0.0.1:9200/_cat/indices/wazuh-alerts-*?v"
> # Empty output = no index = Filebeat problem
>
> sudo head -c 100 /etc/filebeat/wazuh-template.json
> # If "404: Not Found" = template file is corrupt
> ```
>
> Fix — re-download template:
> ```bash
> sudo curl -L -f -o /etc/filebeat/wazuh-template.json \
>   https://raw.githubusercontent.com/wazuh/wazuh/v4.14.5/extensions/elasticsearch/7.x/wazuh-template.json
> sudo chmod go+r /etc/filebeat/wazuh-template.json
> sudo filebeat test config
> sudo systemctl restart filebeat
> sleep 60
> curl -k -u admin:<PASSWORD> "https://127.0.0.1:9200/_cat/indices/wazuh-alerts-*?v"
> # Now shows: wazuh-alerts-4.x-YYYY.MM.DD with doc count
> ```
>
> Time zone note: Wazuh logs UTC. Pakistan is UTC+5. Always use Last 24 hours when debugging.

---

## Phase 7 — Custom Detection Rules

On SOC Server:

```bash
sudo nano /var/ossec/etc/rules/local_rules.xml
```

Replace entire file with:

```xml
<!-- Local rules -->
<!-- Copyright (C) 2015, Wazuh Inc. -->

<group name="local_rules,">

  <!-- SSH Brute Force from internal attacker subnet — MITRE T1110 -->
  <rule id="100001" level="12">
    <if_matched_sid>5760</if_matched_sid>
    <srcip>192.168.56.0/24</srcip>
    <description>Custom SOC Lab: SSH brute force from internal attacker network</description>
    <mitre>
      <id>T1110</id>
    </mitre>
    <group>authentication_failures,pci_dss_10.2.4,pci_dss_10.2.5,</group>
  </rule>

  <!-- Successful login after brute force — MITRE T1110 + T1078 -->
  <rule id="100002" level="15">
    <if_matched_sid>5760</if_matched_sid>
    <if_sid>5715</if_sid>
    <description>Custom SOC Lab: Successful SSH login after brute force - possible compromise!</description>
    <mitre>
      <id>T1110</id>
      <id>T1078</id>
    </mitre>
    <group>authentication_failures,authentication_success,</group>
  </rule>

</group>
```

Validate and restart:

```bash
sudo /var/ossec/bin/wazuh-logtest -V
sudo /var/ossec/bin/wazuh-analysisd -t 2>&1 | tail -5
sudo systemctl restart wazuh-manager
sudo systemctl status wazuh-manager --no-pager | grep Active
```

Run Hydra again. Search dashboard: `rule.id: 100001`

> **Known Issue — ossec.conf broken after nano edit (line 0 XML error):**
>
> Nano can paste new content after the closing </ossec_config> tag, breaking the file.
> Symptom: `Error reading XML file 'etc/ossec.conf': (line 0)`
>
> Diagnose: `sudo tail -30 /var/ossec/etc/ossec.conf`
> If you see content after </ossec_config> or broken tags like `<o<command>` — file is corrupt.
>
> Fix:
> ```bash
> sudo python3 << 'PYEOF'
> with open('/var/ossec/etc/ossec.conf', 'r') as f:
>     content = f.read()
> cut = content.find('</ossec_config>')
> clean = content[:cut] + "\n</ossec_config>\n"
> with open('/var/ossec/etc/ossec.conf', 'w') as f:
>     f.write(clean)
> print("Fixed!")
> PYEOF
> sudo /var/ossec/bin/wazuh-analysisd -t 2>&1
> sudo systemctl restart wazuh-manager
> ```

---

## Phase 8 — Automated Incident Response

On SOC Server, add to ossec.conf inside `<ossec_config>` before `</ossec_config>`:

```bash
sudo nano /var/ossec/etc/ossec.conf
```

```xml
  <command>
    <name>firewall-drop</name>
    <executable>firewall-drop</executable>
    <timeout_allowed>yes</timeout_allowed>
  </command>

  <active-response>
    <command>firewall-drop</command>
    <location>local</location>
    <rules_id>100001</rules_id>
    <timeout>300</timeout>
  </active-response>
```

> **Why firewall-drop and not a custom script?**
> Wazuh 4.x sends JSON via stdin to active-response scripts. Custom scripts using positional
> arguments $1 $2 $3 (old Wazuh 3.x format) silently fail — logged as
> "Active response command not present". The built-in firewall-drop binary handles Wazuh 4.x
> JSON format natively. Always use built-in scripts for IP blocking in Wazuh 4.x.

```bash
sudo /var/ossec/bin/wazuh-analysisd -t 2>&1 | tail -3   # empty = clean
sudo systemctl restart wazuh-manager
sudo systemctl restart wazuh-agent    # on Victim VM
```

Run Hydra. Then on Victim VM:

```bash
sudo iptables -L INPUT -n | grep 192.168.56.30
# Expected: DROP all -- 192.168.56.30 0.0.0.0/0
```

---

## Phase 9 — ML Risk Scoring

```bash
sudo apt install -y python3-pip python3-venv
mkdir -p ~/Mini-SOC-Lab/detection-engine
cd ~/Mini-SOC-Lab/detection-engine
python3 -m venv venv
source venv/bin/activate
pip install pandas scikit-learn numpy
```

Create features.py:

```python
import json, pandas as pd
from datetime import datetime

ALERT_FILE = "/var/ossec/logs/alerts/alerts.json"

def parse_alerts(filepath=ALERT_FILE):
    records = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                records.append(extract_features(json.loads(line)))
            except: continue
    return pd.DataFrame(records)

def extract_features(alert):
    rule, agent, data = alert.get("rule",{}), alert.get("agent",{}), alert.get("data",{})
    try: hour = datetime.fromisoformat(alert.get("timestamp","").replace("Z","+00:00")).hour
    except: hour = 0
    srcip = data.get("srcip","")
    groups = " ".join(rule.get("groups",[]))
    return {
        "rule_id": int(rule.get("id",0)),
        "rule_level": int(rule.get("level",0)),
        "fired_times": int(rule.get("firedtimes",1)),
        "hour_of_day": hour,
        "is_internal_attacker": 1 if srcip.startswith("192.168.56.3") else 0,
        "is_auth_failure": 1 if "authentication" in groups else 0,
        "is_brute_force": 1 if "brute" in groups.lower() or rule.get("id") in ["5760","100001"] else 0,
        "is_rootcheck": 1 if "rootcheck" in groups else 0,
        "agent_id": 1 if agent.get("id") == "001" else 0,
        "description": rule.get("description",""),
    }

if __name__ == "__main__":
    df = parse_alerts()
    print(f"Total alerts: {len(df)}")
```

Create model.py:

```python
import numpy as np, pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import MinMaxScaler
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from features import parse_alerts

FEATURES = ["rule_level","fired_times","hour_of_day","is_internal_attacker",
            "is_auth_failure","is_brute_force","is_rootcheck","agent_id"]

def assign_label(row):
    if row["is_brute_force"]: return 2
    if row["is_auth_failure"] and row["rule_level"] >= 10: return 2
    if row["rule_level"] >= 10: return 2
    if row["rule_level"] >= 7: return 1
    return 0

def risk_score(prob):
    return round(float(np.dot(prob, [0, 50, 100])), 2)

if __name__ == "__main__":
    df = parse_alerts()
    df["label"] = df.apply(assign_label, axis=1)
    X = df[FEATURES].fillna(0)
    scaler = MinMaxScaler()
    X_s = scaler.fit_transform(X)
    model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight="balanced")
    model.fit(X_s, df["label"])
    proba = model.predict_proba(X_s)
    if proba.shape[1] == 2:
        proba = np.hstack([proba, np.zeros((len(proba),1))])
    df["risk_score"] = [risk_score(p) for p in proba]
    df["risk_label"] = df["risk_score"].apply(lambda s: "HIGH" if s>=70 else ("MEDIUM" if s>=30 else "LOW"))
    print("\n=== RISK SUMMARY ===")
    print(df["risk_label"].value_counts())
    print("\n=== FEATURE IMPORTANCE ===")
    for f,i in sorted(zip(FEATURES, model.feature_importances_), key=lambda x: x[1], reverse=True):
        print(f"  {f:<25} {i:.4f}")
```

Run:

```bash
sudo venv/bin/python3 model.py
```

Expected: LOW ~600, MEDIUM ~250, HIGH ~50 | SSH brute force = 100.0/HIGH

---

## Phase 10 — GitHub

```bash
sudo apt install -y git
git config --global user.name "YourUsername"
git config --global user.email "your@email.com"

cd ~/Mini-SOC-Lab
git init
mkdir -p wazuh/rules response attacks reports
sudo cp /var/ossec/etc/rules/local_rules.xml wazuh/rules/
git add .
git commit -m "feat: Mini SOC Lab — Wazuh SIEM, custom rules, auto-response, ML scoring"
git remote add origin https://github.com/<your-username>/Mini-SOC-Lab.git
git branch -M main
git push -u origin main
```

---

## Troubleshooting Index

**Disk full during Wazuh install:**
```bash
sudo apt clean && sudo apt install -y cloud-guest-utils
sudo growpart /dev/sda 3
sudo pvresize /dev/sda3
sudo lvextend -r -l +100%FREE /dev/mapper/ubuntu--vg-ubuntu--lv
df -h
sudo apt --fix-broken install
```

**Indexer AccessDeniedException:**
```bash
sudo chown -R wazuh-indexer:wazuh-indexer /etc/wazuh-indexer/
sudo systemctl restart wazuh-indexer
```

**Dashboard cert missing:**
```bash
sudo mkdir -p /etc/wazuh-dashboard/certs
sudo cp /home/zaig/wazuh-certificates/dashboard*.pem /etc/wazuh-dashboard/certs/
sudo cp /home/zaig/wazuh-certificates/root-ca.pem /etc/wazuh-dashboard/certs/
sudo chown -R wazuh-dashboard:wazuh-dashboard /etc/wazuh-dashboard/certs
sudo find /etc/wazuh-dashboard/certs -type f -exec chmod 400 {} \;
sudo systemctl restart wazuh-dashboard
```

**Filebeat template 404 — no alerts in dashboard:**
```bash
sudo curl -L -f -o /etc/filebeat/wazuh-template.json \
  https://raw.githubusercontent.com/wazuh/wazuh/v4.14.5/extensions/elasticsearch/7.x/wazuh-template.json
sudo filebeat test config && sudo systemctl restart filebeat
sleep 60
curl -k -u admin:<PASSWORD> "https://127.0.0.1:9200/_cat/indices/wazuh-alerts-*?v"
```

**Wrong subnet /21 on enp0s8:** Edit netplan, change to /24, apply.

**Active response not triggering:** Do not use custom shell scripts with positional args in Wazuh 4.x. Use built-in firewall-drop.

**ossec.conf XML broken:**
```bash
sudo python3 -c "
f=open('/var/ossec/etc/ossec.conf','r');c=f.read();f.close()
cut=c.find('</ossec_config>')
open('/var/ossec/etc/ossec.conf','w').write(c[:cut]+'\n</ossec_config>\n')
print('Fixed')"
sudo systemctl restart wazuh-manager
```

**netplan systemd-networkd not running:** Add `renderer: NetworkManager` under `network:` in YAML.

---

## Reference Links

| Resource | URL |
|---|---|
| VirtualBox | https://www.virtualbox.org/wiki/Downloads |
| Ubuntu Server 24.04 | https://ubuntu.com/download/server |
| Ubuntu Desktop | https://ubuntu.com/download/desktop |
| Wazuh Documentation | https://documentation.wazuh.com/current/index.html |
| Wazuh Custom Rules | https://documentation.wazuh.com/current/user-manual/ruleset/custom.html |
| Wazuh Active Response | https://documentation.wazuh.com/current/user-manual/capabilities/active-response/index.html |
| Wazuh Agent Install | https://documentation.wazuh.com/current/installation-guide/wazuh-agent/wazuh-agent-package-linux.html |
| Wazuh Alert Template | https://raw.githubusercontent.com/wazuh/wazuh/v4.14.5/extensions/elasticsearch/7.x/wazuh-template.json |
| Hydra | https://github.com/vanhauser-thc/thc-hydra |
| Nmap | https://nmap.org/download.html |
| scikit-learn | https://scikit-learn.org/stable/ |
| Netplan Docs | https://netplan.readthedocs.io/en/stable/ |
| MITRE T1110 | https://attack.mitre.org/techniques/T1110/ |
| MITRE T1078 | https://attack.mitre.org/techniques/T1078/ |

---

*Built by Muhammad Rehan Khan — Salim Habib University, 6th Semester CS*
*GitHub: https://github.com/dev-rehaann*
