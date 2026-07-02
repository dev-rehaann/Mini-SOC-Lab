# Mini-SOC-Lab

A multi-VM Security Operations Center (SOC) lab built to simulate enterprise-level threat detection, log collection, automated incident response, and ML-based risk scoring — using Wazuh SIEM on a local VirtualBox network.

> **CV Line:** Designed and deployed a multi-VM SOC environment using Wazuh SIEM, Linux telemetry, custom detection rules, automated incident response, and ML-based threat scoring.

---

## Architecture

```
ATTACKER VM (Ubuntu 26.04 Desktop)
    192.168.56.30
         |
         |  SSH Brute Force (Hydra)
         v
VICTIM VM (Ubuntu Server 24.04 LTS)
    192.168.56.20
    Apache2 + OpenSSH + Wazuh Agent
         |
         |  Log forwarding via Wazuh Agent
         v
SOC SERVER VM (Ubuntu Server 24.04 LTS)
    192.168.56.10
    Wazuh Manager + Indexer + Dashboard + Filebeat
         |
         v
    https://192.168.56.10  (Wazuh Dashboard)
```

### VM Specifications

| VM | OS | RAM | CPU | Disk | IP |
|---|---|---|---|---|---|
| SOC Server | Ubuntu Server 24.04 LTS | 6 GB | 2 cores | 25 GB | 192.168.56.10 |
| Victim | Ubuntu Server 24.04 LTS | 2 GB | 1 core | 10 GB | 192.168.56.20 |
| Attacker | Ubuntu 26.04 Desktop | 4 GB | 2 cores | 15 GB | 192.168.56.30 |

### Networking

- All VMs use dual adapters: **NAT** (internet) + **Host-only** (internal lab)
- Host-only network: `192.168.56.0/24` — DHCP disabled, static IPs only
- VirtualBox Host Network Manager: `vboxnet0`

---

## Components

### Wazuh Stack (SOC Server)
- **Wazuh Manager** — receives and analyzes agent logs
- **Wazuh Indexer** — OpenSearch-based storage for alerts
- **Wazuh Dashboard** — visualization and threat hunting
- **Filebeat** — ships `alerts.json` from manager into the indexer

### Victim VM Services
- **OpenSSH Server** — attack surface for brute force simulation
- **Apache2** — web service for future web attack scenarios
- **Fake users** — `testuser`, `adminuser` for realistic attack targets
- **Wazuh Agent** — forwards logs to SOC Server (`192.168.56.10`)

### Attacker VM Tools
- **Hydra** — SSH brute force
- **Nmap** — network reconnaissance

---

## Detection Rules

Custom rules in `/var/ossec/etc/rules/local_rules.xml`:

```xml
<!-- Rule 100001: SSH Brute Force from internal attacker subnet -->
<rule id="100001" level="12">
  <if_matched_sid>5760</if_matched_sid>
  <srcip>192.168.56.0/24</srcip>
  <description>Custom SOC Lab: SSH brute force detected from internal attacker network</description>
  <mitre>
    <id>T1110</id>
  </mitre>
</rule>

<!-- Rule 100002: Successful login after brute force — critical -->
<rule id="100002" level="15">
  <if_matched_sid>5760</if_matched_sid>
  <if_sid>5715</if_sid>
  <description>Custom SOC Lab: Successful SSH login after brute force - possible compromise!</description>
  <mitre>
    <id>T1110</id>
    <id>T1078</id>
  </mitre>
</rule>
```

**MITRE ATT&CK mapping:**
- T1110 — Brute Force
- T1078 — Valid Accounts

---

## Automated Incident Response

Configured in `/var/ossec/etc/ossec.conf` using Wazuh's built-in `firewall-drop` active response:

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

When rule 100001 fires, the attacker IP is automatically blocked via `iptables DROP` on the Victim VM for 300 seconds — no manual intervention required.

**Verified result:**
```
DROP  all  --  192.168.56.30  0.0.0.0/0
```

---

## ML Risk Scoring

Located in `detection-engine/`. A Random Forest classifier trained on 906 real Wazuh alerts to assign a 0–100 risk score to each event.

### Features used

| Feature | Importance |
|---|---|
| rule_level | 0.3126 |
| is_brute_force | 0.1824 |
| is_internal_attacker | 0.1823 |
| is_rootcheck | 0.1514 |
| is_auth_failure | 0.0784 |
| fired_times | 0.0481 |

### Alert distribution (906 total)

| Risk Label | Count |
|---|---|
| LOW | 608 |
| MEDIUM | 246 |
| HIGH | 52 |

SSH brute force events scored **100.0 / HIGH** consistently.

### Files

```
detection-engine/
├── features.py   — parses alerts.json, extracts numeric features
├── model.py      — trains Random Forest, scores all alerts
└── scorer.py     — (planned) real-time scoring daemon
```

---

## Attack Scenarios

### 1. SSH Brute Force

**Tool:** Hydra v9.6  
**Command:**
```bash
hydra -l testuser -P passwords.txt 192.168.56.20 ssh -t 4 -V
```

**Result:**
- Password cracked: `S3cur3T3st@2024`
- Rules fired: `100001` (level 12), `100002` (level 15)
- ML risk score: `100.0` — HIGH
- Automated response: `iptables DROP 192.168.56.30`

**Detection chain:**
```
Hydra → SSH auth failures on Victim
→ /var/log/auth.log
→ Wazuh Agent (rule 5760)
→ Custom rule 100001 (level 12)
→ firewall-drop active response
→ Attacker IP blocked automatically
```

---

## Challenges Faced & Fixes

Real issues encountered during this build — documented for reproducibility.

### 1. Disk Full During Wazuh Install
**Error:** `No space left on device` while unpacking `wazuh-dashboard`  
**Cause:** VirtualBox disk resized to 80 GB but Ubuntu LVM partition still showed 23 GB  
**Fix:**
```bash
sudo growpart /dev/sda 3
sudo pvresize /dev/sda3
sudo lvextend -r -l +100%FREE /dev/mapper/ubuntu--vg-ubuntu--lv
```
Result: Root partition expanded to 77 GB

### 2. Wazuh Dashboard SSL Certificate Missing
**Error:** `ENOENT: no such file or directory, open '/etc/wazuh-dashboard/certs/dashboard-key.pem'`  
**Cause:** Broken install left cert directory empty  
**Fix:**
```bash
sudo mkdir -p /etc/wazuh-dashboard/certs
sudo cp /home/zaig/wazuh-certificates/dashboard.pem /etc/wazuh-dashboard/certs/
sudo cp /home/zaig/wazuh-certificates/dashboard-key.pem /etc/wazuh-dashboard/certs/
sudo cp /home/zaig/wazuh-certificates/root-ca.pem /etc/wazuh-dashboard/certs/
sudo chown -R wazuh-dashboard:wazuh-dashboard /etc/wazuh-dashboard/certs
```

### 3. Wazuh Indexer AccessDeniedException
**Error:** `java.nio.file.AccessDeniedException: /etc/wazuh-indexer/backup`  
**Cause:** Wrong ownership on indexer backup directory after reinstall  
**Fix:** Corrected permissions and ownership on `/etc/wazuh-indexer/backup`

### 4. Filebeat Template Returning 404
**Error:** `could not unmarshal json template: invalid character ':'`  
**Cause:** `/etc/filebeat/wazuh-template.json` contained `404: Not Found` instead of valid JSON (bad download)  
**Fix:**
```bash
sudo curl -L -f -o /etc/filebeat/wazuh-template.json \
  https://raw.githubusercontent.com/wazuh/wazuh/v4.14.5/extensions/elasticsearch/7.x/wazuh-template.json
sudo systemctl restart filebeat
```
After fix: `wazuh-alerts-4.x-2026.07.02` index created with 483 documents

### 5. Victim VM Wrong Subnet Mask
**Error:** `192.168.56.20/21` set during install instead of `/24` — ping to SOC Server failed  
**Fix:** Edited `/etc/netplan/00-installer-config.yaml` to set `/24`, added missing `enp0s8` block manually

### 6. Active Response Script Not Triggering
**Error:** `wazuh-execd: Active response command not present: 'block_ip.sh'`  
**Cause:** Custom `block_ip.sh` used legacy positional argument format (`$1 $2 $3`) — Wazuh 4.x expects JSON via stdin  
**Fix:** Switched to built-in `firewall-drop` binary which is already Wazuh 4.x compatible

### 7. ossec.conf XML Corrupted by Editor
**Error:** `Error reading XML file 'etc/ossec.conf': (line 0)`  
**Cause:** Nano pasted new XML block outside the `</ossec_config>` closing tag, breaking the entire file  
**Fix:** Used Python to programmatically cut at first `</ossec_config>`, append clean block, and rewrite file

---

## Repo Structure

```
Mini-SOC-Lab/
├── architecture/
│   └── (network diagram)
├── wazuh/
│   └── rules/
│       └── local_rules.xml
├── detection-engine/
│   ├── features.py
│   └── model.py
├── response/
│   └── block_ip.sh
├── attacks/
│   └── ssh_bruteforce.md
└── reports/
    └── incident_report.md
```

---

## Skills Demonstrated

- SIEM deployment and configuration (Wazuh 4.14.x all-in-one)
- Linux system administration and networking (netplan, iptables, LVM)
- Custom detection rule authoring with MITRE ATT&CK mapping
- Automated incident response via Wazuh active response
- Attack simulation (Hydra SSH brute force)
- ML-based alert triage using Random Forest (scikit-learn)
- Log pipeline: Agent → Manager → Filebeat → Indexer → Dashboard
- VirtualBox lab design with isolated host-only networking

--- 

<div align="center">

## Author

**Muhammad Rehan Khan**  

Built as a BS Computer Science, Salim Habib University.

GitHub: [dev-rehaann](https://github.com/dev-rehaann)

</div>
