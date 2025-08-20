#!/bin/bash
# Watcher script for WireGuard config reloads in Docker
# Place this script in wireguard_scripts and add to container startup if needed

CONFIG_DIR="/config/wg_confs"
RESTART_DIR="/config"

while true; do
    for signal in "$RESTART_DIR"/restart_*; do
        [ -e "$signal" ] || continue
        iface=$(basename "$signal" | sed 's/^restart_//')
        if [ "$iface" = "all" ]; then
            for conf in "$CONFIG_DIR"/*.conf; do
                intf=$(basename "$conf" .conf)
                echo "[WG-RELOAD] Restarting $intf"
                wg-quick down "$intf" 2>/dev/null
                wg-quick up "$intf"
            done
        else
            echo "[WG-RELOAD] Restarting $iface"
            wg-quick down "$iface" 2>/dev/null
            wg-quick up "$iface"
        fi
        rm -f "$signal"
    done
    sleep 2
done
