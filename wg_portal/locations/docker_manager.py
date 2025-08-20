"""
Утиліти для управління WireGuard через shared volumes
"""
import subprocess
import logging
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class WireGuardDockerManager:

    def add_peer_live(self, device):
        """Додає peer до інтерфейсу wg без перезапуску (live)"""
        try:
            interface = device.location.interface_name
            public_key = device.public_key
            allowed_ip = f"{device.ip_address}/32"
            logger.info(f"[LIVE-PEER] Спроба додати peer: interface={interface}, public_key={public_key}, allowed_ip={allowed_ip}")
            # Використовуємо docker exec для виконання wg set у контейнері
            cmd = [
                "docker", "exec", "wireguard_vpn",
                "wg", "set", interface,
                "peer", public_key,
                "allowed-ips", allowed_ip
            ]
            logger.info(f"[LIVE-PEER] Виконую команду: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            logger.info(f"[LIVE-PEER] stdout: {result.stdout}")
            logger.info(f"[LIVE-PEER] stderr: {result.stderr}")
            logger.info(f"[LIVE-PEER] returncode: {result.returncode}")
            if result.returncode != 0:
                logger.error(f"[LIVE-PEER] wg set error: {result.stderr}")
                return False
            logger.info(f"[LIVE-PEER] Peer {public_key} додано live до {interface}")
            return True
        except Exception as e:
            logger.error(f"[LIVE-PEER] Live add peer error: {str(e)}")
            return False
    """Менеджер для управління WireGuard через shared файлову систему"""
    
    def __init__(self, config_path='/app/wireguard_configs'):
        self.config_path = Path(config_path)
        self.wg_confs_path = self.config_path / 'wg_confs'
        
        # Створюємо каталог якщо не існує
        self.wg_confs_path.mkdir(parents=True, exist_ok=True)
    
    def generate_server_config(self, location):
        """Генерує конфігурацію сервера для локації"""
        try:
            # Отримуємо першу мережу локації
            network = location.networks.first()
            if not network:
                logger.error(f"Локація {location.name} не має мереж")
                return False
            
            # Генеруємо IP сервера з підмережі (останній доступний IP)
            import ipaddress
            network_ip = ipaddress.IPv4Network(network.subnet, strict=False)
            # Використовуємо передостанню IP адресу як IP сервера (остання зарезервована для broadcast)
            server_ip = str(list(network_ip.hosts())[-1])
            
            # Використовуємо інтерфейс з локації
            interface = location.interface_name
            
            config_content = f"""[Interface]
Address = {server_ip}
ListenPort = {network.listen_port}
PrivateKey = {location.private_key}
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth+ -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth+ -j MASQUERADE

"""
            
            # Додаємо всі активні пристрої локації як peer'и
            for device in location.devices.filter(status='active'):
                if device.public_key:
                    config_content += f"""
[Peer]
PublicKey = {device.public_key}
AllowedIPs = {device.ip_address}/32
"""
            
            # Записуємо конфігурацію в shared volume
            config_file = self.wg_confs_path / f"{interface}.conf"
            
            with open(config_file, 'w') as f:
                f.write(config_content)
            
            logger.info(f"Конфігурація для {location.name} записана в {config_file}")
            
            # Створюємо файл-сигнал для перезапуску конкретного інтерфейсу
            restart_signal = self.config_path / f'restart_{interface}'
            restart_signal.touch()
            
            return True
                
        except Exception as e:
            logger.error(f"Помилка генерації конфігурації сервера: {str(e)}")
            return False
    
    def generate_all_active_configs(self):
        """Генерує конфігурації для всіх активних локацій"""
        try:
            from .models import Location
            
            active_locations = Location.objects.filter(is_active=True)
            success_count = 0
            
            for location in active_locations:
                if self.generate_server_config(location):
                    success_count += 1
            
            logger.info(f"Згенеровано конфігурації для {success_count} локацій")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Помилка генерації конфігурацій: {str(e)}")
            return False

    def restart_wireguard(self, interface='all'):
        """Створює сигнал для перезапуску WireGuard"""
        try:
            if interface == 'all':
                # Створюємо сигнал для перезапуску всіх інтерфейсів
                restart_signal = self.config_path / 'restart_all'
                restart_signal.write_text("restart_all_interfaces")
                logger.info("Створено сигнал для перезапуску всіх WireGuard інтерфейсів")
            else:
                # Створюємо файл-сигнал для перезапуску конкретного інтерфейсу
                restart_signal = self.config_path / f'restart_{interface}'
                restart_signal.write_text(f"restart_{interface}")
                logger.info(f"Створено сигнал для перезапуску WireGuard інтерфейсу {interface}")
            
            return True
            
        except Exception as e:
            logger.error(f"Помилка створення сигналу перезапуску: {str(e)}")
            return False
    
    def add_peer_to_server(self, device):
        """Додає peer до конфігурації сервера (через regeneration)"""
        try:
            if not device.public_key:
                logger.error(f"Пристрій {device.name} не має публічного ключа")
                return False
            
            # Перегенеровуємо повну конфігурацію сервера
            return self.generate_server_config(device.location)
                
        except Exception as e:
            logger.error(f"Помилка додавання peer: {str(e)}")
            return False

    def remove_peer_from_server(self, device):
        """Видаляє peer з конфігурації сервера (через regeneration)"""
        try:
            # Перегенеровуємо повну конфігурацію сервера
            return self.generate_server_config(device.location)
                
        except Exception as e:
            logger.error(f"Помилка видалення peer: {str(e)}")
            return False

    def update_docker_environment(self, location):
        """Оновлює змінні середовища Docker для локації"""
        try:
            network = location.networks.first()
            if not network:
                return False
            
            env_file = self.config_path / 'wireguard.env'
            
            env_content = f"""SERVERURL={location.server_ip}
SERVERPORT={network.server_port}
INTERNAL_SUBNET={network.subnet.split('/')[0]}
PEERDNS={location.dns_servers.replace(' ', '')}
INTERFACE={network.interface}
"""
            
            with open(env_file, 'w') as f:
                f.write(env_content)
            
            logger.info(f"Environment файл оновлено для локації {location.name}")
            return True
            
        except Exception as e:
            logger.error(f"Помилка оновлення environment: {str(e)}")
            return False
