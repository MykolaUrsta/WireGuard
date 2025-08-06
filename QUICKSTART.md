# WireGuard Manager - Інструкції по запуску

## Швидкий старт

### Linux/macOS
```bash
chmod +x start.sh
./start.sh
```

### Ручний запуск
```bash
# 1. Скопіюйте налаштування
cp .env.example .env

# 2. Відредагуйте .env файл (змініть паролі та ключі)

# 3. Запустіть контейнери
docker-compose up -d

# 4. Перевірте статус
docker-compose ps
```

## Доступ до системи

- **Веб-інтерфейс**: http://localhost
- **Логін**: admin
- **Пароль**: admin123

## Перші кроки

1. **Увійдіть в систему** з обліковими даними admin/admin123
2. **Змініть пароль адміністратора** 
3. **Налаштуйте 2FA** для безпеки
4. **Створіть конфігурацію WireGuard** для вашого акаунту
5. **Завантажте конфігурацію** або відскануйте QR код

## Структура проекту

```
WireGuardNEW/
├── docker-compose.yml              # Основна конфігурація Docker
├── docker-compose.prod.yml         # Продуктивна конфігурація
├── .env.example                    # Приклад налаштувань
├── start.sh                        # Скрипт запуску (Linux/macOS)
├── README.md                       # Детальна документація
├── wg_portal/                      # Django додаток
│   ├── manage.py                   # Django management
│   ├── requirements.txt            # Python залежності
│   ├── Dockerfile                  # Docker файл для Django
│   ├── entrypoint.sh              # Скрипт запуску Django
│   ├── wireguard_manager/         # Основні налаштування Django
│   │   ├── settings.py            # Налаштування
│   │   ├── urls.py                # URL маршрути
│   │   └── wsgi.py                # WSGI конфігурація
│   ├── accounts/                   # Користувачі та 2FA
│   │   ├── models.py              # Моделі користувачів
│   │   ├── views.py               # Views для автентифікації
│   │   ├── forms.py               # Форми
│   │   ├── urls.py                # URL маршрути
│   │   └── admin.py               # Django admin
│   ├── wireguard_management/      # Керування WireGuard
│   │   ├── models.py              # Моделі WireGuard
│   │   ├── views.py               # Views для WireGuard
│   │   ├── utils.py               # Утиліти для WireGuard
│   │   └── urls.py                # URL маршрути
│   ├── logging/                   # Логування та моніторинг
│   │   ├── models.py              # Моделі логів
│   │   ├── views.py               # Views для логів
│   │   ├── middleware.py          # Middleware для логування
│   │   └── urls.py                # URL маршрути
│   └── templates/                 # HTML шаблони
│       ├── base.html              # Базовий шаблон
│       └── accounts/              # Шаблони для користувачів
│           ├── login.html         # Сторінка входу
│           ├── dashboard.html     # Панель управління
│           ├── setup_2fa.html     # Налаштування 2FA
│           └── verify_2fa.html    # Перевірка 2FA
├── nginx/                         # Nginx конфігурація
│   ├── nginx.conf                 # Основна конфігурація
│   └── conf.d/                    # Конфігурації сайтів
│       └── default.conf           # Конфігурація WireGuard Manager
├── wireguard_scripts/             # Скрипти для WireGuard
│   ├── wg-monitor.sh             # Моніторинг підключень
│   └── wg-2fa.sh                 # 2FA для VPN підключень
└── logs/                          # Логи (створюється автоматично)
```

## Компоненти системи

### 1. Django Web Application (порт 8000)
- Веб-інтерфейс для керування користувачами
- 2FA автентифікація з TOTP
- Панель управління WireGuard конфігураціями
- Логування та моніторинг

### 2. PostgreSQL Database (порт 5432)
- Зберігання користувачів та конфігурацій
- Логи активності та VPN сесій
- Події безпеки

### 3. Redis Cache (порт 6379)
- Кешування для швидкості
- Зберігання сесій
- Тимчасові дані

### 4. WireGuard VPN Server (порт 51820/UDP)
- VPN сервер
- Автоматичне керування конфігураціями
- Моніторинг підключень

### 5. Nginx Reverse Proxy (порт 80/443)
- Reverse proxy для Django
- Обслуговування статичних файлів
- Rate limiting для безпеки

## Основні функції

### Веб-інтерфейс
- ✅ Автентифікація користувачів
- ✅ Двофакторна автентифікація (2FA)
- ✅ Панель управління
- ✅ Створення WireGuard конфігурацій
- ✅ QR коди для швидкого налаштування
- ✅ Завантаження конфігурацій
- ✅ Перегляд статистики та логів

### WireGuard VPN
- ✅ Автоматичне керування клієнтами
- ✅ Динамічне призначення IP адрес
- ✅ Моніторинг підключень
- ✅ 2FA при підключенні до VPN
- ✅ Логування всіх подій

### Безпека
- ✅ TOTP 2FA з QR кодами
- ✅ Логування всіх дій користувачів
- ✅ Моніторинг подій безпеки
- ✅ Rate limiting для захисту від атак
- ✅ Безпечні заголовки HTTP

## Корисні команди

### Docker управління
```bash
# Перегляд статусу
docker-compose ps

# Перегляд логів
docker-compose logs -f
docker-compose logs web
docker-compose logs wireguard

# Перезапуск сервісу
docker-compose restart web

# Зупинка всіх сервісів
docker-compose down

# Повне очищення (видаляє дані!)
docker-compose down -v
```

### Django управління
```bash
# Доступ до Django shell
docker-compose exec web python manage.py shell

# Створення суперкористувача
docker-compose exec web python manage.py createsuperuser

# Міграції бази даних
docker-compose exec web python manage.py migrate

# Збір статичних файлів
docker-compose exec web python manage.py collectstatic
```

### WireGuard управління
```bash
# Перегляд активних підключень
docker-compose exec wireguard wg show

# Перезапуск WireGuard
docker-compose exec wireguard wg-quick down wg0
docker-compose exec wireguard wg-quick up wg0

# Перегляд конфігурації
docker-compose exec wireguard cat /config/wg0.conf
```

### Резервне копіювання
```bash
# Backup бази даних
docker-compose exec db pg_dump -U wireguard_user wireguard_db > backup_$(date +%Y%m%d).sql

# Backup конфігурацій
tar -czf configs_backup_$(date +%Y%m%d).tar.gz ./volumes/wireguard_configs/
```

## Виправлення проблем

### Проблема: Не можу підключитися до VPN
1. Перевірте чи порт 51820/UDP відкритий
2. Перевірте чи створена конфігурація користувача
3. Перевірте логи WireGuard: `docker-compose logs wireguard`

### Проблема: 2FA не працює
1. Перевірте синхронізацію часу на пристрої
2. Переналаштуйте 2FA з новим QR кодом
3. Перевірте логи Django: `docker-compose logs web`

### Проблема: Веб-інтерфейс недоступний
1. Перевірте статус контейнерів: `docker-compose ps`
2. Перевірте логи Nginx: `docker-compose logs nginx`
3. Перевірте логи Django: `docker-compose logs web`

### Проблема: База даних недоступна
1. Перевірте статус PostgreSQL: `docker-compose logs db`
2. Перевірте підключення: `docker-compose exec db psql -U wireguard_user -d wireguard_db`

## Безпека в продуктиві

1. **Змініть всі паролі за замовчуванням**
2. **Налаштуйте HTTPS** з валідними SSL сертифікатами
3. **Обмежте доступ** до адміністративних панелей
4. **Регулярно оновлюйте** Docker образи
5. **Моніторьте логи** безпеки
6. **Налаштуйте backup** бази даних та конфігурацій

---

**Підтримка**: Цей проект створений для освітніх цілей. Для продуктивного використання обов'язково налаштуйте додаткові заходи безпеки.
