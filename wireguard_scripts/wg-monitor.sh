#!/bin/bash

# WireGuard connection monitor script
# This script monitors client connections and logs them

DJANGO_API_URL="http://web:8000/accounts/api/vpn"
LOG_FILE="/var/log/wireguard/connections.log"
WG_INTERFACE="wg0"

# Ensure log directory exists
mkdir -p /var/log/wireguard

# Function to log connection events
log_event() {
    local event_type="$1"
    local client_key="$2"
    local client_ip="$3"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo "[$timestamp] $event_type: Client $client_ip (Key: ${client_key:0:20}...)" >> "$LOG_FILE"
    
    # Send to Django API for processing
    curl -s -X POST "$DJANGO_API_URL/connection-event/" \
        -H "Content-Type: application/json" \
        -d "{
            \"event_type\": \"$event_type\",
            \"client_public_key\": \"$client_key\",
            \"client_ip\": \"$client_ip\",
            \"timestamp\": \"$timestamp\"
        }" > /dev/null 2>&1
}

# Function to get current connections
get_current_connections() {
    wg show "$WG_INTERFACE" dump | tail -n +2 | while read -r line; do
        if [ -n "$line" ]; then
            public_key=$(echo "$line" | cut -f1)
            endpoint=$(echo "$line" | cut -f3)
            latest_handshake=$(echo "$line" | cut -f4)
            
            # Extract IP from endpoint
            client_ip=$(echo "$endpoint" | cut -d':' -f1)
            
            # Check if handshake is recent (within last 3 minutes)
            current_time=$(date +%s)
            if [ "$latest_handshake" != "0" ] && [ $((current_time - latest_handshake)) -lt 180 ]; then
                echo "$public_key,$client_ip,connected"
            else
                echo "$public_key,$client_ip,disconnected"
            fi
        fi
    done
}

# Function to authenticate client connection
authenticate_client() {
    local public_key="$1"
    local client_ip="$2"
    
    # Call Django API for authentication
    response=$(curl -s -X POST "$DJANGO_API_URL/auth/" \
        -H "Content-Type: application/json" \
        -d "{
            \"public_key\": \"$public_key\",
            \"client_ip\": \"$client_ip\"
        }")
    
    # Parse response
    authenticated=$(echo "$response" | grep -o '"authenticated":[^,}]*' | cut -d':' -f2 | tr -d ' "')
    requires_2fa=$(echo "$response" | grep -o '"requires_2fa":[^,}]*' | cut -d':' -f2 | tr -d ' "')
    
    if [ "$authenticated" = "true" ]; then
        return 0  # Allow connection
    elif [ "$requires_2fa" = "true" ]; then
        return 2  # Requires 2FA
    else
        return 1  # Deny connection
    fi
}

# Main monitoring loop
monitor_connections() {
    declare -A previous_state
    
    while true; do
        current_time=$(date +%s)
        declare -A current_state
        
        # Get current connection states
        while IFS=',' read -r pub_key client_ip status; do
            if [ -n "$pub_key" ]; then
                current_state["$pub_key"]="$status"
                
                # Check for state changes
                if [ "${previous_state[$pub_key]}" != "$status" ]; then
                    if [ "$status" = "connected" ]; then
                        log_event "CONNECTED" "$pub_key" "$client_ip"
                    elif [ "$status" = "disconnected" ] && [ "${previous_state[$pub_key]}" = "connected" ]; then
                        log_event "DISCONNECTED" "$pub_key" "$client_ip"
                    fi
                fi
            fi
        done <<< "$(get_current_connections)"
        
        # Update previous state
        for key in "${!current_state[@]}"; do
            previous_state["$key"]="${current_state[$key]}"
        done
        
        # Remove disconnected clients from previous state
        for key in "${!previous_state[@]}"; do
            if [ -z "${current_state[$key]}" ]; then
                unset previous_state["$key"]
            fi
        done
        
        sleep 30  # Check every 30 seconds
    done
}

# Pre-up script - called when WireGuard interface starts
pre_up() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') WireGuard interface $WG_INTERFACE starting up" >> "$LOG_FILE"
}

# Post-up script - called after WireGuard interface is up
post_up() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') WireGuard interface $WG_INTERFACE is up" >> "$LOG_FILE"
    
    # Start connection monitoring in background
    monitor_connections &
    echo $! > /var/run/wireguard-monitor.pid
}

# Pre-down script - called before WireGuard interface goes down
pre_down() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') WireGuard interface $WG_INTERFACE shutting down" >> "$LOG_FILE"
    
    # Stop monitoring
    if [ -f /var/run/wireguard-monitor.pid ]; then
        kill $(cat /var/run/wireguard-monitor.pid) 2>/dev/null
        rm -f /var/run/wireguard-monitor.pid
    fi
}

# Post-down script - called after WireGuard interface is down
post_down() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') WireGuard interface $WG_INTERFACE is down" >> "$LOG_FILE"
}

# Handle script arguments
case "$1" in
    "pre-up")
        pre_up
        ;;
    "post-up")
        post_up
        ;;
    "pre-down")
        pre_down
        ;;
    "post-down")
        post_down
        ;;
    "monitor")
        monitor_connections
        ;;
    "auth")
        authenticate_client "$2" "$3"
        ;;
    *)
        echo "Usage: $0 {pre-up|post-up|pre-down|post-down|monitor|auth <public_key> <client_ip>}"
        exit 1
        ;;
esac
