#!/bin/bash

# Wait for database to be ready
echo "Waiting for database..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "Database started"

# Create migrations for all apps if they don't exist
echo "Creating migrations for all apps..."
python manage.py makemigrations accounts || true
python manage.py makemigrations wireguard_management || true
python manage.py makemigrations audit_logging || true

# Run migrations for auth first (required by other apps)
echo "Running auth migrations..."
python manage.py migrate auth

# Run migrations for all apps
echo "Running all migrations..."
python manage.py migrate

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
python manage.py makemigrations --noinput
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
    
    # Create sample WireGuard network
    echo "🌐 Creating default WireGuard network..."
    
    # Set default values if env vars are not set
    WIREGUARD_SUBNET=${WIREGUARD_SUBNET:-10.0.0.0/24}
    WIREGUARD_SERVER_IP=${WIREGUARD_SERVER_IP:-10.0.0.1}
    WIREGUARD_SERVER_PORT=${WIREGUARD_SERVER_PORT:-51820}
    
    python manage.py shell -c "
from wireguard_management.models import WireGuardNetwork, WireGuardServer
import subprocess

# Create default network if it doesn't exist
if not WireGuardNetwork.objects.exists():
    network = WireGuardNetwork.objects.create(
        name='Default Network',
        network_cidr='$WIREGUARD_SUBNET',
        description='Default WireGuard network for internal use',
        is_active=True
    )
    
    # Generate server keys
    try:
        private_key = subprocess.check_output(['wg', 'genkey'], text=True).strip()
        public_key = subprocess.check_output(['wg', 'pubkey'], input=private_key, text=True).strip()
        
        # Create default server
        server = WireGuardServer.objects.create(
            name='Main Server',
            network=network,
            endpoint='0.0.0.0',
            listen_port=$WIREGUARD_SERVER_PORT,
            public_key=public_key,
            private_key=private_key,
            server_ip='$WIREGUARD_SERVER_IP',
            is_active=True
        )
        print('✅ Default WireGuard network and server created')
        print(f'📋 Network: $WIREGUARD_SUBNET')
        print(f'🖥️ Server IP: $WIREGUARD_SERVER_IP:$WIREGUARD_SERVER_PORT')
    except Exception as e:
        print(f'⚠️ Could not create WireGuard server: {e}')
else:
    print('ℹ️ WireGuard network already exists')
"

    # Mark as initialized
    touch /app/.initialized
    echo "✅ Application initialized successfully"
fi

# Start server
echo "🚀 Starting Django development server..."
echo "📍 Admin panel: http://localhost/admin"
echo "👤 Login: ${ADMIN_USERNAME:-admin} / ${ADMIN_PASSWORD:-admin123}"
echo "🌐 WireGuard Network: ${WIREGUARD_SUBNET:-10.0.0.0/24}"
echo "🖥️ Server: ${WIREGUARD_SERVER_IP:-10.0.0.1}:${WIREGUARD_SERVER_PORT:-51820}"
echo "========================="

exec python manage.py runserver 0.0.0.0:8000

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
# Start Gunicorn
exec gunicorn wireguard_manager.wsgi:application --bind 0.0.0.0:8000 --workers 3
