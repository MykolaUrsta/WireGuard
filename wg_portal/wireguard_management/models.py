from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.utils import timezone
import ipaddress

User = get_user_model()


class WireGuardNetwork(models.Model):
    """Мережа WireGuard"""
    
    name = models.CharField(max_length=100, unique=True, verbose_name='Назва мережі')
    network_cidr = models.CharField(
        max_length=18, 
        verbose_name='CIDR мережі',
        help_text='Наприклад: 10.0.0.0/24'
    )
    description = models.TextField(blank=True, null=True, verbose_name='Опис')
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'WireGuard мережа'
        verbose_name_plural = 'WireGuard мережі'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.network_cidr})"
    
    def get_next_available_ip(self):
        """Отримує наступний доступний IP в мережі"""
        try:
            network = ipaddress.IPv4Network(self.network_cidr)
            used_ips = set()
            
            # Додаємо IP серверів
            for server in self.servers.all():
                if server.server_ip:
                    used_ips.add(ipaddress.IPv4Address(server.server_ip))
            
            # Додаємо IP peer'ів
            for server in self.servers.all():
                for peer in server.peers.all():
                    if peer.ip_address:
                        used_ips.add(ipaddress.IPv4Address(peer.ip_address))
            
            # Знаходимо перший доступний IP
            for ip in network.hosts():
                if ip not in used_ips:
                    return str(ip)
            
            return None
            
        except Exception:
            return None


class WireGuardServer(models.Model):
    """Сервер WireGuard"""
    
    name = models.CharField(max_length=100, verbose_name='Назва сервера')
    network = models.ForeignKey(WireGuardNetwork, on_delete=models.CASCADE, related_name='servers')
    
    # Мережні налаштування
    endpoint = models.CharField(max_length=255, verbose_name='Endpoint', help_text='IP або домен сервера')
    listen_port = models.PositiveIntegerField(default=51820, verbose_name='Порт')
    server_ip = models.GenericIPAddressField(verbose_name='IP сервера')
    
    # Ключі
    public_key = models.TextField(verbose_name='Публічний ключ')
    private_key = models.TextField(verbose_name='Приватний ключ')
    
    # Додаткові налаштування
    dns_servers = models.CharField(max_length=255, default='8.8.8.8, 1.1.1.1', verbose_name='DNS сервери')
    keep_alive = models.PositiveIntegerField(default=25, verbose_name='Keep Alive')
    mtu = models.PositiveIntegerField(default=1420, verbose_name='MTU')
    
    # Статистика
    total_peers = models.PositiveIntegerField(default=0, verbose_name='Всього peer\'ів')
    active_peers = models.PositiveIntegerField(default=0, verbose_name='Активних peer\'ів')
    
    # Стан
    is_active = models.BooleanField(default=True, verbose_name='Активний')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'WireGuard сервер'
        verbose_name_plural = 'WireGuard сервери'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.endpoint}:{self.listen_port})"
    
    def update_peer_counts(self):
        """Оновлює лічильники peer'ів"""
        self.total_peers = self.peers.count()
        self.active_peers = self.peers.filter(is_active=True).count()
        self.save(update_fields=['total_peers', 'active_peers'])


class WireGuardPeer(models.Model):
    """Peer (клієнт) WireGuard"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wireguard_peers')
    server = models.ForeignKey(WireGuardServer, on_delete=models.CASCADE, related_name='peers')
    
    # Основна інформація
    name = models.CharField(max_length=100, verbose_name='Назва конфігурації')
    ip_address = models.GenericIPAddressField(verbose_name='IP адреса')
    
    # Ключі
    public_key = models.TextField(verbose_name='Публічний ключ')
    private_key = models.TextField(verbose_name='Приватний ключ')
    
    # Налаштування
    allowed_ips = models.CharField(max_length=255, default='0.0.0.0/0, ::/0', verbose_name='Дозволені IP')
    keep_alive = models.PositiveIntegerField(blank=True, null=True, verbose_name='Keep Alive')
    
    # Статистика трафіку
    bytes_sent = models.BigIntegerField(default=0, verbose_name='Відправлено байт')
    bytes_received = models.BigIntegerField(default=0, verbose_name='Отримано байт')
    last_handshake = models.DateTimeField(blank=True, null=True, verbose_name='Останнє з\'єднання')
    
    # Стан
    is_active = models.BooleanField(default=True, verbose_name='Активний')
    is_online = models.BooleanField(default=False, verbose_name='Онлайн')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'WireGuard peer'
        verbose_name_plural = 'WireGuard peer\'и'
        ordering = ['-created_at']
        unique_together = ['user', 'server', 'name']
    
    def __str__(self):
        return f"{self.user.username} - {self.name} ({self.ip_address})"
    
    def get_sent_mb(self):
        """Відправлено в MB"""
        return round(self.bytes_sent / 1024 / 1024, 2)
    
    def get_received_mb(self):
        """Отримано в MB"""
        return round(self.bytes_received / 1024 / 1024, 2)
    
    def get_total_mb(self):
        """Загальний трафік в MB"""
        return self.get_sent_mb() + self.get_received_mb()
    
    @property
    def is_online(self):
        """Перевіряє чи peer онлайн (handshake менше 3 хвилин тому)"""
        if not self.last_handshake:
            return False
        return (timezone.now() - self.last_handshake).total_seconds() < 180
    
    def generate_config(self):
        """Генерує конфігурацію для peer'а"""
        config = f"""[Interface]
PrivateKey = {self.private_key}
Address = {self.ip_address}/32
DNS = {self.server.dns_servers}
MTU = {self.server.mtu}

[Peer]
PublicKey = {self.server.public_key}
Endpoint = {self.server.endpoint}:{self.server.listen_port}
AllowedIPs = {self.allowed_ips}
PersistentKeepalive = {self.keep_alive or self.server.keep_alive}
"""
        return config
