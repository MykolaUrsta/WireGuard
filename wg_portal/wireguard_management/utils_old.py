import subprocess
import os
import ipaddress
import secrets
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from django.conf import settings
from django.utils import timezone
from .models import WireGuardServer, WireGuardPeer, WireGuardConfigTemplate
from accounts.models import CustomUser
import logging

logger = logging.getLogger(__name__)


class WireGuardManager:
    """Клас для керування WireGuard конфігураціями та клієнтами"""
    
    def __init__(self):
        self.config_path = getattr(settings, 'WIREGUARD_CONFIG_PATH', '/app/wireguard_configs')
        self.server_interface = getattr(settings, 'WIREGUARD_INTERFACE', 'wg0')
        self.server_ip = getattr(settings, 'WIREGUARD_SERVER_IP', '10.13.13.1')
        self.server_port = getattr(settings, 'WIREGUARD_SERVER_PORT', 51820)
        self.subnet = ipaddress.IPv4Network(getattr(settings, 'WIREGUARD_SUBNET', '10.13.13.0/24'))
    
    def generate_keypair(self):
        """Генерує пару ключів WireGuard"""
        try:
            # Генеруємо приватний ключ
            private_key_bytes = os.urandom(32)
            private_key = base64.b64encode(private_key_bytes).decode('utf-8')
            
            # Генеруємо публічний ключ
            private_key_obj = x25519.X25519PrivateKey.from_private_bytes(private_key_bytes)
            public_key_bytes = private_key_obj.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            public_key = base64.b64encode(public_key_bytes).decode('utf-8')
            
            return private_key, public_key
        except Exception as e:
            logger.error(f"Помилка генерації ключів: {e}")
            raise
    
    def get_next_available_ip(self, server):
        """Повертає наступну доступну IP адресу для клієнта"""
        try:
            # Отримуємо всі зайняті IP
            used_ips = set(WireGuardPeer.objects.filter(server=server).values_list('client_ip', flat=True))
            used_ips.add(str(self.subnet.network_address))  # Адреса мережі
            used_ips.add(str(self.subnet.broadcast_address))  # Broadcast адреса
            used_ips.add(self.server_ip)  # IP сервера
            
            # Знаходимо першу вільну IP
            for ip in self.subnet.hosts():
                if str(ip) not in used_ips:
                    return str(ip)
            
            raise ValueError("Немає доступних IP адрес у мережі")
        except Exception as e:
            logger.error(f"Помилка отримання IP: {e}")
            raise
    
    def create_peer(self, user, server=None, template=None):
        """Створює нового клієнта WireGuard"""
        try:
            if not server:
                server = WireGuardServer.objects.filter(is_active=True).first()
                if not server:
                    raise ValueError("Немає активного сервера WireGuard")
            
            if not template:
                template = WireGuardConfigTemplate.objects.filter(is_default=True).first()
                if not template:
                    template = WireGuardConfigTemplate.objects.first()
            
            # Перевіряємо чи користувач вже має peer
            if hasattr(user, 'wireguard_peer'):
                raise ValueError("Користувач вже має конфігурацію WireGuard")
            
            # Генеруємо ключі
            private_key, public_key = self.generate_keypair()
            
            # Отримуємо IP для клієнта
            client_ip = self.get_next_available_ip(server)
            
            # Створюємо peer
            peer = WireGuardPeer.objects.create(
                user=user,
                server=server,
                public_key=public_key,
                private_key=private_key,
                client_ip=client_ip,
                allowed_ips=template.allowed_ips if template else '0.0.0.0/0',
                persistent_keepalive=template.persistent_keepalive if template else 25
            )
            
            # Оновлюємо користувача
            user.is_wireguard_enabled = True
            user.wireguard_public_key = public_key
            user.wireguard_private_key = private_key
            user.wireguard_ip = client_ip
            user.wireguard_config = peer.config_content
            user.save()
            
            # Створюємо файл конфігурації
            self.create_config_file(peer)
            
            # Оновлюємо конфігурацію сервера
            self.update_server_config(server)
            
            logger.info(f"Створено WireGuard peer для користувача {user.username}")
            return peer
            
        except Exception as e:
            logger.error(f"Помилка створення peer: {e}")
            raise
    
    def delete_peer(self, user):
        """Видаляє клієнта WireGuard"""
        try:
            if not hasattr(user, 'wireguard_peer'):
                raise ValueError("Користувач не має конфігурації WireGuard")
            
            peer = user.wireguard_peer
            server = peer.server
            
            # Видаляємо файл конфігурації
            config_file = os.path.join(self.config_path, f"{user.username}.conf")
            if os.path.exists(config_file):
                os.remove(config_file)
            
            # Видаляємо peer
            peer.delete()
            
            # Оновлюємо користувача
            user.is_wireguard_enabled = False
            user.wireguard_public_key = None
            user.wireguard_private_key = None
            user.wireguard_ip = None
            user.wireguard_config = None
            user.save()
            
            # Оновлюємо конфігурацію сервера
            self.update_server_config(server)
            
            logger.info(f"Видалено WireGuard peer для користувача {user.username}")
            
        except Exception as e:
            logger.error(f"Помилка видалення peer: {e}")
            raise
    
    def create_config_file(self, peer):
        """Створює файл конфігурації для клієнта"""
        try:
            os.makedirs(self.config_path, exist_ok=True)
            
            config_file = os.path.join(self.config_path, f"{peer.user.username}.conf")
            with open(config_file, 'w') as f:
                f.write(peer.config_content)
            
            # Встановлюємо права доступу
            os.chmod(config_file, 0o600)
            
        except Exception as e:
            logger.error(f"Помилка створення файлу конфігурації: {e}")
            raise
    
    def update_server_config(self, server):
        """Оновлює конфігурацію сервера з усіма активними клієнтами"""
        try:
            server_config = f"""[Interface]
PrivateKey = {server.private_key}
Address = {self.server_ip}/32
ListenPort = {server.listen_port}
PostUp = iptables -A FORWARD -i {self.server_interface} -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i {self.server_interface} -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

"""
            
            # Додаємо всіх активних клієнтів
            for peer in server.peers.filter(is_active=True):
                server_config += f"""[Peer]
PublicKey = {peer.public_key}
AllowedIPs = {peer.client_ip}/32
"""
                if peer.preshared_key:
                    server_config += f"PresharedKey = {peer.preshared_key}\n"
                server_config += "\n"
            
            # Зберігаємо конфігурацію сервера
            server_config_file = os.path.join(self.config_path, f"{self.server_interface}.conf")
            with open(server_config_file, 'w') as f:
                f.write(server_config)
            
            # Встановлюємо права доступу
            os.chmod(server_config_file, 0o600)
            
            # Перезапускаємо WireGuard інтерфейс
            self.restart_wireguard_interface()
            
        except Exception as e:
            logger.error(f"Помилка оновлення конфігурації сервера: {e}")
            raise
    
    def restart_wireguard_interface(self):
        """Перезапускає WireGuard інтерфейс"""
        try:
            # Зупиняємо інтерфейс
            subprocess.run(['wg-quick', 'down', self.server_interface], 
                         capture_output=True, text=True, check=False)
            
            # Запускаємо інтерфейс
            result = subprocess.run(['wg-quick', 'up', self.server_interface], 
                                  capture_output=True, text=True, check=True)
            
            logger.info(f"WireGuard інтерфейс {self.server_interface} перезапущено")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Помилка перезапуску WireGuard: {e.stderr}")
            raise
    
    def get_peer_statistics(self, peer):
        """Отримує статистику для клієнта"""
        try:
            result = subprocess.run(['wg', 'show', self.server_interface, 'dump'], 
                                  capture_output=True, text=True, check=True)
            
            for line in result.stdout.strip().split('\n')[1:]:  # Пропускаємо заголовок
                parts = line.split('\t')
                if len(parts) >= 6 and parts[0] == peer.public_key:
                    peer.last_handshake = timezone.datetime.fromtimestamp(int(parts[2])) if parts[2] != '0' else None
                    peer.bytes_received = int(parts[3])
                    peer.bytes_sent = int(parts[4])
                    peer.save()
                    break
                    
        except subprocess.CalledProcessError as e:
            logger.error(f"Помилка отримання статистики: {e}")
    
    def is_peer_connected(self, peer):
        """Перевіряє чи клієнт підключений"""
        try:
            if not peer.last_handshake:
                return False
            
            # Вважаємо підключеним, якщо останній handshake був менше 3 хвилин тому
            time_diff = timezone.now() - peer.last_handshake
            return time_diff.total_seconds() < 180
            
        except Exception:
            return False
