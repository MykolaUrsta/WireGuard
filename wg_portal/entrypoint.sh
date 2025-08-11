#!/bin/bash

set -e

echo "=== WireGuard Portal Starting ==="

# Wait for database
echo "⏳ Waiting for database..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "✅ Database connected"

# Wait for Redis
echo "⏳ Waiting for Redis..."
while ! nc -z redis 6379; do
  sleep 0.1
done
echo "✅ Redis connected"

# Check if this is first run
FIRST_RUN=false
if [ ! -f "/app/.initialized" ]; then
    FIRST_RUN=true
    echo "🚀 First run detected - initializing application..."
fi

# Run migrations
echo "📊 Running database migrations..."
# Create migrations for all apps
python manage.py makemigrations accounts --noinput || true
python manage.py makemigrations wireguard_management --noinput || true
python manage.py makemigrations locations --noinput || true
python manage.py makemigrations audit_logging --noinput || true
# Run all migrations
python manage.py migrate --noinput

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput --clear

# Create superuser if it doesn't exist
if [ "$FIRST_RUN" = true ]; then
    echo "👤 Creating superuser..."
    
    # Set default values if env vars are not set
    ADMIN_USERNAME=${ADMIN_USERNAME:-admin}
    ADMIN_EMAIL=${ADMIN_EMAIL:-admin@localhost}
    ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin123}
    ADMIN_FIRST_NAME=${ADMIN_FIRST_NAME:-System}
    ADMIN_LAST_NAME=${ADMIN_LAST_NAME:-Administrator}
    ADMIN_DEPARTMENT=${ADMIN_DEPARTMENT:-IT}
    ADMIN_POSITION=${ADMIN_POSITION:-Administrator}
    
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    user = User.objects.create_superuser(
        username='$ADMIN_USERNAME',
        email='$ADMIN_EMAIL', 
        password='$ADMIN_PASSWORD',
        first_name='$ADMIN_FIRST_NAME',
        last_name='$ADMIN_LAST_NAME',
        department='$ADMIN_DEPARTMENT',
        position='$ADMIN_POSITION'
    )
    print('✅ Superuser created: $ADMIN_USERNAME / $ADMIN_PASSWORD')
else:
    print('ℹ️ Superuser already exists')
"
    


    # Mark as initialized
    touch /app/.initialized
    echo "✅ Application initialized successfully"
fi

# Setup cron for stats updates (every minute) - run as root for Docker access
echo "⏰ Setting up stats sync cron job..."
(crontab -l 2>/dev/null || true; echo "* * * * * cd /app && sudo -u root python manage.py fast_sync_stats --quiet >/dev/null 2>&1") | crontab -
service cron start || true

# Run initial stats sync as root
echo "📊 Running initial stats synchronization..."
sudo -u root python manage.py fast_sync_stats --quiet || true

# Start background stats sync process (configurable interval) - run as root
SYNC_INTERVAL=${SYNC_INTERVAL:-1}
echo "🔄 Starting background stats sync process (every ${SYNC_INTERVAL} seconds)..."
(
    while true; do
        sleep $SYNC_INTERVAL
        sudo -u root python manage.py fast_sync_stats --quiet >/dev/null 2>&1 || true
    done
) &

# Start server
echo "🚀 Starting Django development server..."
echo "📍 Admin panel: http://localhost/admin"
echo "👤 Login: ${ADMIN_USERNAME:-admin} / ${ADMIN_PASSWORD:-admin123}"
echo "🌐 Create WireGuard networks through Locations panel"
echo "========================="

exec python manage.py runserver 0.0.0.0:8000
