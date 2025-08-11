#!/usr/bin/env python3
"""
Скрипт для автоматичного оновлення docker-compose.yml
на основі налаштувань локацій Django
"""

import os
import sys
import django
from pathlib import Path

# Додаємо шлях до Django проекту
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wireguard_manager.settings')
django.setup()

from locations.models import Location
import yaml
import logging

logger = logging.getLogger(__name__)

def update_docker_compose():
    """Оновлює docker-compose.yml з налаштуваннями активної локації"""
    try:
        # Знаходимо активну локацію
        location = Location.objects.filter(is_active=True).first()
        if not location:
            logger.warning("Активна локація не знайдена")
            return False
        
        network = location.networks.first()
        if not network:
            logger.warning(f"Локація {location.name} не має мереж")
            return False
        
        # Читаємо docker-compose.yml
        compose_path = Path('/home/mrmiko/WireGuard/docker-compose.yml')
        
        with open(compose_path, 'r') as f:
            compose_data = yaml.safe_load(f)
        
        # Оновлюємо змінні середовища для WireGuard
        if 'services' in compose_data and 'wireguard' in compose_data['services']:
            env_list = compose_data['services']['wireguard']['environment']
            
            # Конвертуємо у словник для легшого оновлення
            env_dict = {}
            for item in env_list:
                if '=' in item:
                    key, value = item.split('=', 1)
                    env_dict[key.strip()] = value.strip()
            
            # Оновлюємо значення
            env_dict['SERVERURL'] = location.server_ip
            env_dict['SERVERPORT'] = str(network.server_port)
            env_dict['INTERNAL_SUBNET'] = network.subnet.split('/')[0]  # Тільки IP
            env_dict['PEERDNS'] = location.dns_servers.replace(' ', '')
            
            # Конвертуємо назад у список
            compose_data['services']['wireguard']['environment'] = [
                f"{key}={value}" for key, value in env_dict.items()
            ]
            
            # Зберігаємо файл
            with open(compose_path, 'w') as f:
                yaml.dump(compose_data, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"Docker-compose оновлено для локації {location.name}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Помилка оновлення docker-compose: {str(e)}")
        return False

if __name__ == '__main__':
    update_docker_compose()
