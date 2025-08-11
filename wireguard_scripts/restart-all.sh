#!/bin/bash

# Скрипт для автоматичного запуску всіх WireGuard інтерфейсів
# Викликається з Django при зміні конфігурацій

CONFIG_DIR="/config/wg_confs"
LOG_FILE="/config/logs/wireguard-multi.log"

# Створюємо директорію для логів
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "$(date): $1" | tee -a "$LOG_FILE"
}

log "=== Початок оновлення WireGuard конфігурацій ==="

# Зупиняємо всі існуючі інтерфейси
for iface in $(ip link show | grep -o 'wg[0-9]*'); do
    if [ -n "$iface" ]; then
        log "Зупинка інтерфейсу $iface"
        wg-quick down "$iface" 2>/dev/null || true
    fi
done

# Запускаємо інтерфейси з конфігураційних файлів
if [ -d "$CONFIG_DIR" ]; then
    for config_file in "$CONFIG_DIR"/wg*.conf; do
        if [ -f "$config_file" ]; then
            interface=$(basename "$config_file" .conf)
            log "Запуск інтерфейсу $interface з $config_file"
            
            if wg-quick up "$config_file"; then
                log "✓ Інтерфейс $interface успішно запущено"
            else
                log "✗ Помилка запуску інтерфейсу $interface"
            fi
        fi
    done
else
    log "Директорія конфігурацій $CONFIG_DIR не знайдена"
fi

# Перевіряємо статус інтерфейсів
log "=== Статус WireGuard інтерфейсів ==="
for iface in $(ip link show | grep -o 'wg[0-9]*'); do
    if [ -n "$iface" ]; then
        status=$(wg show "$iface" 2>/dev/null || echo "недоступний")
        log "Інтерфейс $iface: $status"
    fi
done

log "=== Завершення оновлення ==="
