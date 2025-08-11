#!/bin/bash

# Скрипт для оновлення статистики WireGuard peer'ів
cd /home/mrmiko/WireGuard

# Запускаємо команду оновлення через Docker
docker compose exec -T web python manage.py update_peer_status

# Логуємо результат
echo "$(date): Peer status updated" >> /var/log/wireguard-stats.log
