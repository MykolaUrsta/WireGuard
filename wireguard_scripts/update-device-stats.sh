#!/bin/bash

# Скрипт для швидкого оновлення статистик WireGuard пристроїв
# Додати до crontab: * * * * * /app/wireguard_scripts/update-device-stats.sh

cd /app

# Швидко оновлюємо статистики пристроїв з WireGuard серверів (тихий режим)
python manage.py fast_sync_stats --quiet

# Зберігаємо поточну статистику для моніторингу (кожні 5 хвилин)
MINUTE=$(date +%M)
if [ $((MINUTE % 5)) -eq 0 ]; then
    python manage.py save_peer_stats
fi
