#!/bin/bash

# WireGuard Manager Quick Start Script
# Цей скрипт допоможе швидко запустити систему

set -e

echo "🚀 WireGuard Manager - Швидкий старт"
echo "====================================="

# Перевірка наявності Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не встановлений. Будь ласка, встановіть Docker та Docker Compose"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose не встановлений. Будь ласка, встановіть Docker Compose"
    exit 1
fi

echo "✅ Docker та Docker Compose знайдені"

# Створення .env файлу якщо його немає
if [ ! -f .env ]; then
    echo "📝 Створення .env файлу..."
    cp .env.example .env
    echo "✅ .env файл створений з прикладу"
    echo "⚠️  Рекомендуємо змінити SECRET_KEY та паролі у .env файлі"
fi

# Створення необхідних директорій
echo "📁 Створення директорій..."
mkdir -p logs
mkdir -p ssl
chmod +x wireguard_scripts/*.sh

echo "✅ Директорії створені"

# Зупинка існуючих контейнерів
echo "🛑 Зупинка існуючих контейнерів..."
docker-compose down --remove-orphans 2>/dev/null || true

# Запуск сервісів
echo "🚀 Запуск сервісів..."
docker-compose up -d

echo "⏳ Очікування запуску сервісів..."
sleep 10

# Перевірка статусу
echo "📊 Статус сервісів:"
docker-compose ps

# Перевірка логів
echo "📜 Перевірка логів Django..."
timeout 30 docker-compose logs web | grep -E "(server is ready|Quit the server|started|error)" || true

echo ""
echo "🎉 Система WireGuard Manager запущена!"
echo ""
echo "📱 Доступ до веб-інтерфейсу:"
echo "   🌐 HTTP: http://localhost"
echo "   👤 Логін: admin"
echo "   🔑 Пароль: admin123"
echo ""
echo "🔧 Корисні команди:"
echo "   📊 Статус:      docker compose ps"
echo "   📜 Логи:        docker compose logs -f"
echo "   🛑 Зупинка:     docker compose down"
echo "   🔄 Перезапуск:  docker compose restart"
echo ""
echo "📚 Документація та налаштування: README.md"
echo ""
echo "⚠️  ВАЖЛИВО:"
echo "   1. Змініть пароль адміністратора після першого входу"
echo "   2. Налаштуйте 2FA для безпеки"
echo "   3. Для продуктивного використання налаштуйте HTTPS"
echo ""

# Перевірка доступності веб-інтерфейсу
echo "🔍 Перевірка доступності веб-інтерфейсу..."
for i in {1..30}; do
    if curl -s http://localhost > /dev/null 2>&1; then
        echo "✅ Веб-інтерфейс доступний: http://localhost"
        break
    fi
    echo "⏳ Очікування ($i/30)..."
    sleep 2
done

echo "🏁 Запуск завершено!"
