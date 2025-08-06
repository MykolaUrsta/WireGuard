import subprocess
import os
import logging
from django.conf import settings
from .models import WireGuardPeer, WireGuardServer

logger = logging.getLogger(__name__)


def generate_wireguard_config(peer):
    """Генерує конфігурацію WireGuard для peer'а"""
    
    server = peer.server
    
    config = f"""[Interface]
PrivateKey = {peer.private_key}
Address = {peer.ip_address}/32
DNS = {server.dns_servers}
MTU = {server.mtu}

[Peer]
PublicKey = {server.public_key}
Endpoint = {server.endpoint}:{server.listen_port}
AllowedIPs = {peer.allowed_ips}
PersistentKeepalive = {server.keep_alive}
"""
    
    return config.strip()


def update_server_config(server):
    """Оновлює конфігурацію WireGuard сервера"""
    
    try:
        # Базова конфігурація сервера
        config_lines = [
            "[Interface]",
            f"PrivateKey = {server.private_key}",
            f"Address = {server.server_ip}/24",
            f"ListenPort = {server.listen_port}",
            f"DNS = {server.dns_servers}",
            "",
            "# Post up rules",
            "PostUp = iptables -A FORWARD -i wg0 -j ACCEPT",
            "PostUp = iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE",
            "",
            "# Post down rules", 
            "PostDown = iptables -D FORWARD -i wg0 -j ACCEPT",
            "PostDown = iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE",
            ""
        ]
        
        # Додаємо активних peer'ів
        active_peers = server.peers.filter(is_active=True)
        
        for peer in active_peers:
            config_lines.extend([
                "# " + peer.user.username + " - " + peer.name,
                "[Peer]",
                f"PublicKey = {peer.public_key}",
                f"AllowedIPs = {peer.ip_address}/32",
                ""
            ])
        
        # Записуємо конфігурацію у файл
        config_content = "\n".join(config_lines)
        
        # Створюємо директорію якщо не існує
        config_dir = "/app/wireguard_configs"
        os.makedirs(config_dir, exist_ok=True)
        
        config_file = f"{config_dir}/wg_{server.id}.conf"
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        logger.info(f"Конфігурацію сервера {server.name} оновлено: {config_file}")
        
        # Оновлюємо лічильники peer'ів
        server.update_peer_counts()
        
        return config_file
        
    except Exception as e:
        logger.error(f"Помилка оновлення конфігурації сервера {server.name}: {e}")
        raise


def get_wireguard_status():
    """Отримує статус WireGuard інтерфейсів"""
    
    try:
        # Запускаємо wg show для отримання статусу
        result = subprocess.run(['wg', 'show'], capture_output=True, text=True)
        
        if result.returncode == 0:
            return result.stdout
        else:
            logger.warning(f"Помилка отримання статусу WireGuard: {result.stderr}")
            return ""
            
    except Exception as e:
        logger.error(f"Помилка виконання wg show: {e}")
        return ""


def update_peer_traffic_stats():
    """Оновлює статистику трафіку peer'ів з WireGuard"""
    
    try:
        # Отримуємо статистику з wg show
        result = subprocess.run(['wg', 'show', 'all', 'transfer'], capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.warning("Не вдалося отримати статистику трафіку WireGuard")
            return
        
        # Парсимо вивід wg show
        lines = result.stdout.strip().split('\n')
        current_interface = None
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('interface:'):
                current_interface = line.split(':')[1].strip()
                continue
            
            if line and current_interface:
                parts = line.split()
                if len(parts) >= 3:
                    public_key = parts[0]
                    bytes_received = int(parts[1]) if parts[1] != '(none)' else 0
                    bytes_sent = int(parts[2]) if parts[2] != '(none)' else 0
                    
                    # Оновлюємо статистику peer'а
                    try:
                        peer = WireGuardPeer.objects.get(public_key=public_key)
                        peer.bytes_received = bytes_received
                        peer.bytes_sent = bytes_sent
                        peer.save(update_fields=['bytes_received', 'bytes_sent'])
                        
                        # Оновлюємо статистику користувача
                        user = peer.user
                        user.total_download = bytes_received
                        user.total_upload = bytes_sent
                        user.save(update_fields=['total_download', 'total_upload'])
                        
                    except WireGuardPeer.DoesNotExist:
                        logger.warning(f"Peer з public key {public_key} не знайдено в БД")
        
        logger.info("Статистику трафіку peer'ів оновлено")
        
    except Exception as e:
        logger.error(f"Помилка оновлення статистики трафіку: {e}")


def restart_wireguard_interface(interface_name):
    """Перезапускає WireGuard інтерфейс"""
    
    try:
        # Зупиняємо інтерфейс
        subprocess.run(['wg-quick', 'down', interface_name], check=False)
        
        # Запускаємо інтерфейс
        result = subprocess.run(['wg-quick', 'up', interface_name], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"WireGuard інтерфейс {interface_name} перезапущено")
            return True
        else:
            logger.error(f"Помилка перезапуску інтерфейсу {interface_name}: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Помилка перезапуску WireGuard інтерфейсу {interface_name}: {e}")
        return False
