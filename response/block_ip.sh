#!/bin/bash
# Wazuh Active Response — Block attacker IP via iptables
# Triggered by rule 100001 (SSH brute force)

LOCAL=$(dirname "$0")
cd "$LOCAL" || exit 1

ACTION=$1
USER=$2
IP=$3

if [ "$ACTION" = "add" ]; then
    logger -t wazuh-block "Blocking IP: $IP"
    iptables -I INPUT -s "$IP" -j DROP
    echo "$(date) BLOCKED: $IP" >> /var/log/wazuh-blocks.log
elif [ "$ACTION" = "delete" ]; then
    logger -t wazuh-block "Unblocking IP: $IP"
    iptables -D INPUT -s "$IP" -j DROP
    echo "$(date) UNBLOCKED: $IP" >> /var/log/wazuh-blocks.log
fi

exit 0

