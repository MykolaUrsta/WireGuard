#!/bin/bash

# WireGuard 2FA Authentication Script
# This script handles 2FA authentication for WireGuard connections

DJANGO_API_URL="http://web:8000/accounts/api/vpn"
LOG_FILE="/var/log/wireguard/2fa.log"
TEMP_DIR="/tmp/wireguard-2fa"

# Create necessary directories
mkdir -p "$TEMP_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log events
log_message() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
}

# Function to show 2FA prompt to user
show_2fa_prompt() {
    local user_id="$1"
    local client_ip="$2"
    
    # Create a temporary HTML file for 2FA prompt
    local prompt_file="$TEMP_DIR/2fa_prompt_${user_id}_$(date +%s).html"
    
    cat > "$prompt_file" << EOF
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WireGuard 2FA</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
        }
        .container {
            background: white;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
            text-align: center;
            max-width: 400px;
            width: 90%;
        }
        .logo {
            font-size: 3rem;
            color: #667eea;
            margin-bottom: 1rem;
        }
        h1 {
            color: #333;
            margin-bottom: 1rem;
        }
        .input-group {
            margin-bottom: 1rem;
        }
        input[type="text"] {
            width: 100%;
            padding: 12px;
            font-size: 18px;
            text-align: center;
            border: 2px solid #ddd;
            border-radius: 5px;
            letter-spacing: 5px;
            font-family: monospace;
        }
        input[type="text"]:focus {
            outline: none;
            border-color: #667eea;
        }
        .btn {
            background: #667eea;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            width: 100%;
            margin: 5px 0;
        }
        .btn:hover {
            background: #5a6fd8;
        }
        .btn.cancel {
            background: #dc3545;
        }
        .btn.cancel:hover {
            background: #c82333;
        }
        .info {
            color: #666;
            font-size: 14px;
            margin-top: 1rem;
        }
        .error {
            color: #dc3545;
            margin-top: 1rem;
        }
        .success {
            color: #28a745;
            margin-top: 1rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🛡️</div>
        <h1>WireGuard VPN</h1>
        <h2>Двофакторна автентифікація</h2>
        
        <form id="2faForm">
            <div class="input-group">
                <input type="text" 
                       id="token" 
                       name="token" 
                       placeholder="000000" 
                       maxlength="6" 
                       pattern="[0-9]{6}"
                       autocomplete="off"
                       autofocus>
            </div>
            
            <button type="submit" class="btn">Підтвердити</button>
            <button type="button" class="btn cancel" onclick="cancelAuth()">Скасувати</button>
        </form>
        
        <div class="info">
            Введіть 6-значний код з додатка автентифікації
        </div>
        
        <div id="message"></div>
    </div>

    <script>
        const userIdInput = document.createElement('input');
        userIdInput.type = 'hidden';
        userIdInput.name = 'user_id';
        userIdInput.value = '$user_id';
        document.getElementById('2faForm').appendChild(userIdInput);

        const clientIpInput = document.createElement('input');
        clientIpInput.type = 'hidden';
        clientIpInput.name = 'client_ip';
        clientIpInput.value = '$client_ip';
        document.getElementById('2faForm').appendChild(clientIpInput);

        document.getElementById('token').addEventListener('input', function(e) {
            e.target.value = e.target.value.replace(/[^0-9]/g, '');
            if (e.target.value.length === 6) {
                document.getElementById('2faForm').dispatchEvent(new Event('submit'));
            }
        });

        document.getElementById('2faForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            const token = document.getElementById('token').value;
            const userId = '$user_id';
            const clientIp = '$client_ip';
            
            if (token.length !== 6) {
                showMessage('Введіть 6-значний код', 'error');
                return;
            }
            
            // Send 2FA verification request
            fetch('$DJANGO_API_URL/2fa/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    user_id: userId,
                    token: token,
                    client_ip: clientIp
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.authenticated) {
                    showMessage('Автентифікація успішна! Підключення до VPN...', 'success');
                    setTimeout(() => {
                        window.close();
                        // Signal success to parent process
                        fetch('/tmp/wireguard-2fa/auth_result_$user_id', {
                            method: 'POST',
                            body: 'SUCCESS'
                        });
                    }, 2000);
                } else {
                    showMessage('Невірний код автентифікації', 'error');
                    document.getElementById('token').value = '';
                    document.getElementById('token').focus();
                }
            })
            .catch(error => {
                showMessage('Помилка з\'єднання з сервером', 'error');
            });
        });

        function cancelAuth() {
            // Signal cancellation to parent process
            fetch('/tmp/wireguard-2fa/auth_result_$user_id', {
                method: 'POST',
                body: 'CANCELLED'
            });
            window.close();
        }

        function showMessage(text, type) {
            const messageDiv = document.getElementById('message');
            messageDiv.textContent = text;
            messageDiv.className = type;
        }
    </script>
</body>
</html>
EOF

    echo "$prompt_file"
}

# Function to verify 2FA token
verify_2fa_token() {
    local user_id="$1"
    local token="$2"
    local client_ip="$3"
    
    log_message "INFO" "Verifying 2FA token for user $user_id from $client_ip"
    
    response=$(curl -s -X POST "$DJANGO_API_URL/2fa/" \
        -H "Content-Type: application/json" \
        -d "{
            \"user_id\": \"$user_id\",
            \"token\": \"$token\",
            \"client_ip\": \"$client_ip\"
        }")
    
    authenticated=$(echo "$response" | grep -o '"authenticated":[^,}]*' | cut -d':' -f2 | tr -d ' "')
    
    if [ "$authenticated" = "true" ]; then
        log_message "INFO" "2FA verification successful for user $user_id"
        return 0
    else
        log_message "WARN" "2FA verification failed for user $user_id"
        return 1
    fi
}

# Function to handle 2FA authentication flow
handle_2fa_auth() {
    local user_id="$1"
    local client_ip="$2"
    local timeout="${3:-300}"  # 5 minutes default timeout
    
    log_message "INFO" "Starting 2FA authentication for user $user_id from $client_ip"
    
    # Create result file
    local result_file="$TEMP_DIR/auth_result_$user_id"
    rm -f "$result_file"
    
    # Show 2FA prompt (this would typically open a browser or show a system notification)
    prompt_file=$(show_2fa_prompt "$user_id" "$client_ip")
    
    # For this example, we'll use a simple timeout-based approach
    # In a real implementation, you might use a web interface or mobile app
    
    local start_time=$(date +%s)
    local max_time=$((start_time + timeout))
    
    echo "2FA Required for VPN Connection"
    echo "User ID: $user_id"
    echo "Client IP: $client_ip"
    echo "Please complete 2FA authentication within $timeout seconds"
    echo "Prompt file: $prompt_file"
    
    # Wait for result or timeout
    while [ $(date +%s) -lt $max_time ]; do
        if [ -f "$result_file" ]; then
            result=$(cat "$result_file")
            rm -f "$result_file"
            rm -f "$prompt_file"
            
            case "$result" in
                "SUCCESS")
                    log_message "INFO" "2FA authentication successful for user $user_id"
                    return 0
                    ;;
                "CANCELLED")
                    log_message "INFO" "2FA authentication cancelled by user $user_id"
                    return 1
                    ;;
                *)
                    log_message "WARN" "Unknown 2FA result: $result"
                    return 1
                    ;;
            esac
        fi
        
        sleep 1
    done
    
    # Timeout reached
    rm -f "$prompt_file"
    log_message "WARN" "2FA authentication timeout for user $user_id"
    return 1
}

# Function to check if user requires 2FA
check_2fa_requirement() {
    local public_key="$1"
    local client_ip="$2"
    
    response=$(curl -s -X POST "$DJANGO_API_URL/auth/" \
        -H "Content-Type: application/json" \
        -d "{
            \"public_key\": \"$public_key\",
            \"client_ip\": \"$client_ip\"
        }")
    
    requires_2fa=$(echo "$response" | grep -o '"requires_2fa":[^,}]*' | cut -d':' -f2 | tr -d ' "')
    user_id=$(echo "$response" | grep -o '"user_id":[^,}]*' | cut -d':' -f2 | tr -d ' "')
    
    if [ "$requires_2fa" = "true" ] && [ -n "$user_id" ]; then
        echo "$user_id"
        return 0
    else
        return 1
    fi
}

# Main function
main() {
    local action="$1"
    local public_key="$2"
    local client_ip="$3"
    local token="$4"
    
    case "$action" in
        "check")
            # Check if 2FA is required
            if user_id=$(check_2fa_requirement "$public_key" "$client_ip"); then
                echo "2FA_REQUIRED:$user_id"
                exit 0
            else
                echo "NO_2FA_REQUIRED"
                exit 0
            fi
            ;;
        "authenticate")
            # Perform 2FA authentication
            local user_id="$public_key"  # In this context, public_key is actually user_id
            if handle_2fa_auth "$user_id" "$client_ip"; then
                echo "AUTHENTICATED"
                exit 0
            else
                echo "AUTHENTICATION_FAILED"
                exit 1
            fi
            ;;
        "verify")
            # Verify 2FA token
            local user_id="$public_key"  # In this context, public_key is actually user_id
            if verify_2fa_token "$user_id" "$client_ip" "$token"; then
                echo "TOKEN_VALID"
                exit 0
            else
                echo "TOKEN_INVALID"
                exit 1
            fi
            ;;
        *)
            echo "Usage: $0 {check|authenticate|verify} <public_key|user_id> <client_ip> [token]"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
