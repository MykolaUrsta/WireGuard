#!/bin/bash

# WireGuard Manager - Універсальний скрипт розгортання
# Підтримує різні режими: повна установка, швидке розгортання, оновлення

set -e

DOMAIN="wg-portal.itc.gov.ua"
EMAIL="admin@itc.gov.ua"
MODE="full"

# Парсинг аргументів
while [[ $# -gt 0 ]]; do
    case $1 in
        --deploy)
            MODE="deploy"
            shift
            ;;
        --update)
            MODE="update"
            shift
            ;;
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --email)
            EMAIL="$2"
            shift 2
            ;;
        -h|--help)
            echo "Використання: $0 [ОПЦІЇ]"
            echo ""
            echo "РЕЖИМИ:"
            echo "  (без опцій)  Повна установка з нуля"
            echo "  --deploy     Швидке розгортання на налаштованому сервері"
            echo "  --update     Швидке оновлення з кешуванням"
            echo ""
            echo "ОПЦІЇ:"
            echo "  --domain     Домен для SSL сертифікату (за замовчуванням: wg-portal.itc.gov.ua)"
            echo "  --email      Email для Let's Encrypt (за замовчуванням: admin@itc.gov.ua)"
            echo "  -h, --help   Показати цю довідку"
            echo ""
            echo "ПРИКЛАДИ:"
            echo "  sudo $0                    # Повна установка"
            echo "  $0 --deploy               # Швидке розгортання"
            echo "  $0 --update               # Тільки оновлення"
            exit 0
            ;;
        *)
            echo "Невідома опція: $1"
            echo "Використайте -h або --help для довідки"
            exit 1
            ;;
    esac
done

# Визначення заголовка в залежності від режиму
case $MODE in
    "full")
        TITLE="🚀 WireGuard Manager - Повна установка з нуля"
        ;;
    "deploy")
        TITLE="⚡ WireGuard Manager - Швидке розгортання"
        ;;
    "update")
        TITLE="🔄 WireGuard Manager - Швидке оновлення"
        ;;
esac

echo "$TITLE"
echo "================================================="
echo ""

if [ "$MODE" = "full" ]; then
    echo "Цей скрипт виконає:"
    echo "✓ Перевірку системних вимог"
    echo "✓ Встановлення Docker та Docker Compose (якщо потрібно)"
    echo "✓ Створення необхідних директорій"
    echo "✓ Збірку та запуск всіх контейнерів"
    echo "✓ Отримання SSL сертифікату від Let's Encrypt"
    echo "✓ Налаштування HTTP/3"
elif [ "$MODE" = "deploy" ]; then
    echo "Цей скрипт виконає:"
    echo "✓ Перевірку Docker"
    echo "✓ Зупинку існуючих контейнерів"
    echo "✓ Збірку та запуск всіх контейнерів"
    echo "✓ Отримання SSL сертифікату (якщо потрібно)"
elif [ "$MODE" = "update" ]; then
    echo "Цей скрипт виконає:"
    echo "✓ Швидку збірку з кешуванням"
    echo "✓ Оновлення тільки змінених контейнерів"
    echo "✓ Перезапуск сервісів"
fi
echo ""

# Функція перевірки ROOT прав (тільки для повної установки)
check_root() {
    if [ "$MODE" = "full" ] && [ "$EUID" -ne 0 ]; then
        echo "❌ Повна установка потребує ROOT права. Запустіть з sudo"
        exit 1
    fi
}

# Функція встановлення Docker
install_docker() {
    echo "🐳 Встановлення Docker..."
    
    # Оновлення пакетів
    apt-get update
    
    # Встановлення необхідних пакетів
    apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # Додавання офіційного GPG ключа Docker
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    
    # Додавання репозиторію Docker
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Встановлення Docker
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    
    # Додавання користувача в групу docker
    if [ "$SUDO_USER" ]; then
        usermod -aG docker $SUDO_USER
        echo "✓ Користувач $SUDO_USER доданий в групу docker"
    fi
    
    # Запуск Docker
    systemctl start docker
    systemctl enable docker
    
    echo "✓ Docker встановлено та запущено"
}

# Функція перевірки Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        if [ "$MODE" = "full" ]; then
            echo "⚠️  Docker не знайдено. Встановлюємо..."
            install_docker
        else
            echo "❌ Docker не встановлений. Використайте: sudo $0 (без опцій) для повної установки"
            exit 1
        fi
    else
        echo "✓ Docker вже встановлений"
    fi
    
    if ! docker compose version &> /dev/null; then
        echo "❌ Docker Compose не знайдено"
        exit 1
    else
        echo "✓ Docker Compose доступний"
    fi
}

# Функція створення директорій
create_directories() {
    echo "📁 Створення необхідних директорій..."
    
    mkdir -p logs
    mkdir -p ssl/certbot/conf
    mkdir -p ssl/certbot/www
    mkdir -p ssl/nginx
    
    # Встановлення прав
    chmod 755 logs
    chmod 755 ssl
    
    echo "✓ Директорії створено"
}

# Функція зупинки існуючих контейнерів
stop_existing() {
    echo "🛑 Зупинка існуючих контейнерів..."
    
    if docker compose ps -q 2>/dev/null | grep -q .; then
        docker compose down
        echo "✓ Існуючі контейнери зупинено"
    else
        echo "✓ Активних контейнерів не знайдено"
    fi
}

# Функція швидкого оновлення
quick_update() {
    echo "🔄 Швидке оновлення з кешуванням..."
    
    # Швидка збірка з кешем
    echo "   Збираємо тільки змінені образи..."
    docker compose build
    
    # Оновлення тільки змінених контейнерів
    echo "   Оновлюємо контейнери..."
    docker compose up -d --remove-orphans
    
    echo "✓ Оновлення завершено"
}

# Функція збірки та запуску
build_and_start() {
    echo "🔨 Збірка та запуск контейнерів..."
    
    # Збірка з кешем
    echo "   Збираємо образи..."
    docker compose build --parallel
    
    # Запуск
    echo "   Запускаємо контейнери..."
    docker compose up -d
    
    echo "✓ Контейнери запущено"
}

# Функція отримання SSL сертифікату
setup_ssl() {
    echo "🔐 Налаштування SSL сертифікату..."
    
    # Перевірка доступності домену
    echo "   Перевіряємо доступність домену $DOMAIN..."
    if ! curl -s -I http://$DOMAIN >/dev/null 2>&1; then
        echo "⚠️  Домен $DOMAIN недоступний. Пропускаємо SSL..."
        return 0
    fi
    
    # Отримання сертифікату
    echo "   Отримуємо SSL сертифікат..."
    docker run --rm \
        -v $(pwd)/ssl/certbot/conf:/etc/letsencrypt \
        -v $(pwd)/ssl/certbot/www:/var/www/certbot \
        certbot/certbot \
        certonly --webroot \
        --webroot-path=/var/www/certbot \
        --email $EMAIL \
        --agree-tos \
        --no-eff-email \
        -d $DOMAIN
    
    if [ $? -eq 0 ]; then
        echo "✓ SSL сертифікат отримано"
        
        # Перезапуск nginx з SSL
        echo "   Перезапускаємо nginx з SSL..."
        docker compose restart nginx
        echo "✓ Nginx перезапущено з SSL"
    else
        echo "⚠️  Помилка отримання SSL сертифікату"
    fi
}

# Функція відображення статусу
show_status() {
    echo ""
    echo "📊 Статус системи:"
    echo "=================="
    
    sleep 3
    docker compose ps
    
    echo ""
    echo "🌐 Доступ до системи:"
    echo "====================="
    echo "HTTP:  http://$DOMAIN"
    echo "HTTPS: https://$DOMAIN"
    echo ""
    echo "👤 Дані для входу:"
    echo "=================="
    echo "Логін:    admin"
    echo "Email:    admin@example.com"
    echo "Пароль:   admin123"
    echo ""
    echo "🔧 Корисні команди:"
    echo "==================="
    echo "Перегляд логів:     docker compose logs -f"
    echo "Перезапуск:         docker compose restart"
    echo "Зупинка:            docker compose down"
    echo "Швидке оновлення:   ./install.sh --update"
    echo "Швидке розгортання: ./install.sh --deploy"
    echo "Повна установка:    sudo ./install.sh"
    echo ""
}

# Основна функція
main() {
    if [ "$MODE" != "update" ]; then
        echo "Почкаємо розгортання через 3 секунди..."
        sleep 3
    fi
    
    check_root
    check_docker
    
    if [ "$MODE" = "update" ]; then
        # Режим швидкого оновлення
        quick_update
        echo ""
        echo "🎉 Оновлення завершено!"
        echo "======================"
        return 0
    fi
    
    if [ "$MODE" = "full" ]; then
        create_directories
    fi
    
    stop_existing
    
    if [ "$MODE" = "update" ]; then
        quick_update
    else
        build_and_start
    fi
    
    echo ""
    echo "⏳ Очікуємо запуску сервісів (30 секунд)..."
    sleep 30
    
    if [ "$MODE" = "full" ]; then
        setup_ssl
    fi
    
    show_status
    
    echo ""
    echo "🎉 Розгортання завершено!"
    echo "========================="
    echo ""
    echo "Система WireGuard Manager готова до використання!"
}

# Запуск
main
