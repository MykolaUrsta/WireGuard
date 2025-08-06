# WireGuard Manager з Django

Повнофункціональна система керування WireGuard VPN з веб-інтерфейсом Django, двофакторною автентифікацією та детальним логуванням.

## 🚀 Особливості

- **Веб-інтерфейс Django** для керування користувачами та конфігураціями
- **Двофакторна автентифікація (2FA)** з Google Authenticator
- **Автоматичне логування** підключень та відключень VPN
- **2FA при підключенні до VPN** через додаток
- **Безпечна архітектура** з Nginx reverse proxy
- **PostgreSQL база даних** для зберігання даних
- **Redis** для кешування та сесій
- **Docker Compose** для легкого розгортання

## 📋 Компоненти системи

- **Django Web Application** - основний веб-інтерфейс
- **WireGuard VPN Server** - VPN сервер
- **PostgreSQL** - база даних
- **Redis** - кешування та сесії
- **Nginx** - reverse proxy та load balancer

## 🛠️ Встановлення та запуск

### Передумови

- Docker та Docker Compose
- Git

### Крок 1: Клонування репозиторію

```bash
git clone <repository-url>
cd WireGuardNEW
```

### Крок 2: Налаштування змінних середовища

Створіть файл `.env` у корені проекту:

```env
# Django settings
SECRET_KEY=your-very-secret-key-change-this-in-production
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# Database settings
DB_NAME=wireguard_db
DB_USER=wireguard_user
DB_PASSWORD=wireguard_password_2024
DB_HOST=db
DB_PORT=5432

# Redis settings
REDIS_URL=redis://redis:6379/0

# WireGuard settings
WIREGUARD_SERVER_IP=10.13.13.1
WIREGUARD_SERVER_PORT=51820
WIREGUARD_SUBNET=10.13.13.0/24
WIREGUARD_INTERFACE=wg0
```

### Крок 3: Запуск системи

```bash
# Запуск всіх сервісів
docker-compose up -d

# Перевірка статусу
docker-compose ps

# Перегляд логів
docker-compose logs -f web
```

### Крок 4: Ініціалізація

Система автоматично:
- Створить базу даних та таблиці
- Створить суперкористувача (admin/admin123)
- Налаштує статичні файли

## 🔧 Перший запуск

1. **Відкрийте веб-інтерфейс**: http://localhost
2. **Увійдіть як адміністратор**: admin / admin123
3. **Налаштуйте 2FA** для безпеки
4. **Створіть конфігурацію WireGuard** для вашого акаунту

## 📱 Налаштування 2FA

1. Увійдіть в систему
2. Перейдіть до "Налаштування 2FA"
3. Відскануйте QR код в додатку автентифікації:
   - Google Authenticator
   - Authy
   - Microsoft Authenticator
4. Введіть код підтвердження
5. Збережіть резервні коди

## 🔐 Підключення до VPN

### Автоматичне налаштування (QR код)

1. Створіть конфігурацію WireGuard у веб-інтерфейсі
2. Відскануйте QR код в додатку WireGuard
3. При першому підключенні з'явиться запит 2FA
4. Введіть код з додатка автентифікації

### Ручне налаштування

1. Завантажте файл конфігурації `.conf`
2. Імпортуйте в додаток WireGuard
3. Підключіться до VPN

## 📊 Моніторинг та логування

### Веб-інтерфейс

- Панель управління з статистикою
- Логи активності користувачів
- VPN сесії та статистика трафіку
- Події безпеки

### Файлові логи

```bash
# Django application logs
docker-compose exec web tail -f /app/logs/wireguard.log

# WireGuard connection logs
docker-compose exec wireguard tail -f /var/log/wireguard/connections.log

# Nginx access logs
docker-compose exec nginx tail -f /var/log/nginx/access.log
```

## 🛡️ Безпека

### Рекомендації

1. **Змініть паролі за замовчуванням**
2. **Увімкніть 2FA для всіх користувачів**
3. **Використовуйте HTTPS** (налаштуйте SSL сертифікати)
4. **Регулярно оновлюйте систему**
5. **Моніторьте логи безпеки**

### SSL/TLS (HTTPS)

Для продуктивного використання увімкніть HTTPS:

1. Отримайте SSL сертифікати (Let's Encrypt, купівля)
2. Розмістіть сертифікати в `./ssl/`
3. Розкоментуйте HTTPS конфігурацію в `nginx/conf.d/default.conf`
4. Перезапустіть nginx: `docker-compose restart nginx`

## 🔧 Адміністрування

### Керування користувачами

```bash
# Створення суперкористувача
docker-compose exec web python manage.py createsuperuser

# Django admin панель
http://localhost/admin/
```

### Керування WireGuard

```bash
# Перегляд активних підключень
docker-compose exec wireguard wg show

# Перезапуск WireGuard
docker-compose exec wireguard wg-quick down wg0
docker-compose exec wireguard wg-quick up wg0
```

### Резервне копіювання

```bash
# Backup database
docker-compose exec db pg_dump -U wireguard_user wireguard_db > backup.sql

# Backup configurations
tar -czf configs_backup.tar.gz ./wireguard_configs/
```

## 🐛 Розв'язання проблем

### Часті проблеми

1. **Неможливо підключитися до VPN**
   - Перевірте чи увімкнена конфігурація користувача
   - Перевірте брандмауер (порт 51820/UDP)
   - Перевірте логи WireGuard

2. **2FA не працює**
   - Перевірте синхронізацію часу на пристрої
   - Переналаштуйте 2FA з новим QR кодом
   - Перевірте підключення до інтернету

3. **Помилки веб-інтерфейсу**
   - Перевірте логи Django
   - Перевірте підключення до бази даних
   - Перевірте Redis

### Перегляд логів

```bash
# Всі сервіси
docker-compose logs

# Конкретний сервіс
docker-compose logs web
docker-compose logs wireguard
docker-compose logs db
```

## 📝 API Endpoints

### VPN Authentication

- `POST /accounts/api/vpn/auth/` - Автентифікація клієнта
- `POST /accounts/api/vpn/2fa/` - Перевірка 2FA
- `POST /accounts/api/vpn/connection-event/` - Логування подій

### Приклад використання API

```bash
# Автентифікація клієнта
curl -X POST http://localhost/accounts/api/vpn/auth/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user123",
    "public_key": "public_key_here"
  }'

# Перевірка 2FA
curl -X POST http://localhost/accounts/api/vpn/2fa/ \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "1",
    "token": "123456"
  }'
```

## 🤝 Підтримка

### Структура проекту

```
WireGuardNEW/
├── docker-compose.yml          # Docker Compose конфігурація
├── wg_portal/                  # Django додаток
│   ├── accounts/               # Система користувачів та 2FA
│   ├── wireguard_management/   # Керування WireGuard
│   ├── logging/                # Логування та моніторинг
│   └── templates/             # HTML шаблони
├── nginx/                     # Nginx конфігурація
├── wireguard_scripts/         # Скрипти для WireGuard
└── README.md                  # Цей файл
```

### Розробка

Для розробки встановіть залежності локально:

```bash
cd wg_portal
pip install -r requirements.txt
python manage.py runserver
```

## 📄 Ліцензія

Цей проект розповсюджується під ліцензією MIT. Дивіться файл LICENSE для деталей.

## 🔄 Оновлення

```bash
# Оновлення системи
git pull
docker-compose pull
docker-compose up -d --build

# Міграція бази даних (якщо потрібно)
docker-compose exec web python manage.py migrate
```

---

**Примітка**: Цей проект призначений для освітніх та тестових цілей. Для продуктивного використання обов'язково налаштуйте додаткові заходи безпеки.
