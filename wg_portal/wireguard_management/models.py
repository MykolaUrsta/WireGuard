
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.utils import timezone
import ipaddress

class PeerMonitoring(models.Model):
    """Історія трафіку peer'а (пристрою) для моніторингу активності"""
    peer = models.ForeignKey('WireGuardPeer', on_delete=models.CASCADE, related_name='monitoring')
    timestamp = models.DateTimeField(auto_now_add=True)
    bytes_sent = models.BigIntegerField(default=0)
    bytes_received = models.BigIntegerField(default=0)

    class Meta:
        verbose_name = 'Моніторинг peer''а'
        verbose_name_plural = 'Моніторинг peer''ів'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.peer} - {self.timestamp}"

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
    connected_at = models.DateTimeField(blank=True, null=True, verbose_name='Час підключення')
    
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
    
    def get_connection_duration(self):
        """Повертає тривалість підключення в секундах"""
        if not self.connected_at or not self.is_online:
            return 0
        return int((timezone.now() - self.connected_at).total_seconds())
    
    def get_connection_time_formatted(self):
        """Повертає відформатований час підключення"""
        duration = self.get_connection_duration()
        if duration == 0:
            return "Не підключено"
        
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
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


class WireGuardTunnel(models.Model):
    """Тунель WireGuard"""
    
    STATUS_CHOICES = [
        ('active', 'Активний'),
        ('inactive', 'Неактивний'),
        ('error', 'Помилка'),
    ]
    
    name = models.CharField(max_length=100, unique=True, verbose_name='Назва тунелю')
    interface_name = models.CharField(max_length=20, default='wg0', verbose_name='Інтерфейс')
    server = models.ForeignKey(WireGuardServer, on_delete=models.CASCADE, related_name='tunnels')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive')
    is_auto_start = models.BooleanField(default=True, verbose_name='Автозапуск')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_started = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'WireGuard тунель'
        verbose_name_plural = 'WireGuard тунелі'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.interface_name})"
    
    def start(self):
        """Запускає тунель"""
        # Логіка запуску тунелю
        pass
    
    def stop(self):
        """Зупиняє тунель"""
        # Логіка зупинки тунелю
        pass
    
    def restart(self):
        """Перезапускає тунель"""
        self.stop()
        self.start()


class DeviceTOTP(models.Model):
    """TOTP налаштування для пристрою"""
    
    device = models.OneToOneField(WireGuardPeer, on_delete=models.CASCADE, related_name='totp')
    secret_key = models.CharField(max_length=32, verbose_name='Секретний ключ')
    is_enabled = models.BooleanField(default=False, verbose_name='Увімкнено')
    backup_tokens = models.JSONField(default=list, verbose_name='Резервні токени')
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'TOTP налаштування'
        verbose_name_plural = 'TOTP налаштування'
    
    def __str__(self):
        return f"TOTP для {self.device.name}"
    
    def generate_qr_uri(self):
        """Генерує URI для QR коду"""
        from urllib.parse import quote
        issuer = "WireGuard Panel"
        account = f"{self.device.name}@{self.device.server.network.name}"
        return f"otpauth://totp/{quote(account)}?secret={self.secret_key}&issuer={quote(issuer)}"


class FirewallRule(models.Model):
    """Правило фаєрволу"""
    
    ACTION_CHOICES = [
        ('allow', 'Дозволити'),
        ('deny', 'Заборонити'),
        ('log', 'Логувати'),
    ]
    
    PROTOCOL_CHOICES = [
        ('tcp', 'TCP'),
        ('udp', 'UDP'),
        ('icmp', 'ICMP'),
        ('any', 'Будь-який'),
    ]
    
    DIRECTION_CHOICES = [
        ('in', 'Вхідний'),
        ('out', 'Вихідний'),
        ('both', 'Обидва'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='Назва правила')
    network = models.ForeignKey(WireGuardNetwork, on_delete=models.CASCADE, related_name='firewall_rules')
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, default='allow')
    protocol = models.CharField(max_length=10, choices=PROTOCOL_CHOICES, default='any')
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default='both')
    
    source_ip = models.CharField(max_length=100, blank=True, verbose_name='IP джерела')
    source_port = models.CharField(max_length=20, blank=True, verbose_name='Порт джерела')
    destination_ip = models.CharField(max_length=100, blank=True, verbose_name='IP призначення')
    destination_port = models.CharField(max_length=20, blank=True, verbose_name='Порт призначення')
    
    is_enabled = models.BooleanField(default=True, verbose_name='Увімкнено')
    priority = models.IntegerField(default=100, verbose_name='Пріоритет')
    description = models.TextField(blank=True, verbose_name='Опис')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Правило фаєрволу'
        verbose_name_plural = 'Правила фаєрволу'
        ordering = ['priority', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.action} {self.protocol})"
    
    def to_iptables_rule(self):
        """Конвертує в правило iptables"""
        # Логіка генерації iptables правила
        pass


class NetworkMonitoring(models.Model):
    """Моніторинг мережі"""
    
    network = models.ForeignKey(WireGuardNetwork, on_delete=models.CASCADE, related_name='monitoring')
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Статистика
    total_devices = models.IntegerField(default=0)
    active_devices = models.IntegerField(default=0)
    total_traffic_bytes = models.BigIntegerField(default=0)
    
    # Системна інформація
    cpu_usage = models.FloatField(null=True, blank=True)
    memory_usage = models.FloatField(null=True, blank=True)
    disk_usage = models.FloatField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Моніторинг мережі'
        verbose_name_plural = 'Моніторинг мереж'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Моніторинг {self.network.name} - {self.timestamp}"
