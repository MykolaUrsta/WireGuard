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
        unique=True,
        validators=[RegexValidator(
            regex=r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$',
            message='Введіть коректний CIDR (наприклад: 10.13.13.0/24)'
        )],
        verbose_name='Мережа CIDR'
    )
    description = models.TextField(blank=True, verbose_name='Опис')
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'WireGuard Мережа'
        verbose_name_plural = 'WireGuard Мережі'
    
    def __str__(self):
        return f"{self.name} ({self.network_cidr})"
    
    def get_next_available_ip(self):
        """Отримати наступний доступний IP в мережі"""
        network = ipaddress.ip_network(self.network_cidr)
        used_ips = set()
        
        # Додаємо IP сервера
        if hasattr(self, 'server'):
            used_ips.add(ipaddress.ip_address(self.server.server_ip))
        
        # Додаємо IP клієнтів
        for peer in self.peers.all():
            if peer.ip_address:
                used_ips.add(ipaddress.ip_address(peer.ip_address))
        
        # Знаходимо перший вільний IP
        for ip in network.hosts():
            if ip not in used_ips:
                return str(ip)
        
        raise ValueError("Немає доступних IP адрес в мережі")


class WireGuardServer(models.Model):
    """Модель WireGuard сервера"""
    
    name = models.CharField(max_length=100, unique=True, verbose_name='Назва сервера')
    network = models.OneToOneField(
        WireGuardNetwork, 
        on_delete=models.CASCADE,
        related_name='server',
        verbose_name='Мережа'
    )
    public_key = models.TextField(verbose_name='Публічний ключ')
    private_key = models.TextField(verbose_name='Приватний ключ')
    server_ip = models.GenericIPAddressField(verbose_name='IP сервера')
    endpoint = models.CharField(max_length=255, verbose_name='Endpoint (domain:port)')
    listen_port = models.PositiveIntegerField(default=51820, verbose_name='Порт')
    dns_servers = models.CharField(
        max_length=255, 
        default='1.1.1.1,8.8.8.8',
        verbose_name='DNS сервери'
    )
    keep_alive = models.PositiveIntegerField(default=25, verbose_name='Keep Alive')
    mtu = models.PositiveIntegerField(default=1420, verbose_name='MTU')
    
    # Статистика сервера
    total_peers = models.PositiveIntegerField(default=0, verbose_name='Загальна кількість peer\'ів')
    active_peers = models.PositiveIntegerField(default=0, verbose_name='Активні peer\'и')
    
    is_active = models.BooleanField(default=True, verbose_name='Активний')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'WireGuard Сервер'
        verbose_name_plural = 'WireGuard Сервери'
    
    def __str__(self):
        return self.name
    
    def update_peer_counts(self):
        """Оновити лічильники peer'ів"""
        self.total_peers = self.peers.count()
        self.active_peers = self.peers.filter(is_active=True).count()
        self.save(update_fields=['total_peers', 'active_peers'])


class WireGuardPeer(models.Model):
    """Модель клієнта WireGuard (peer)"""
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='wireguard_peers',
        verbose_name='Користувач'
    )
    server = models.ForeignKey(
        WireGuardServer,
        on_delete=models.CASCADE,
        related_name='peers',
        verbose_name='Сервер'
    )
    
    name = models.CharField(max_length=100, verbose_name='Назва конфігурації')
    public_key = models.TextField(verbose_name='Публічний ключ')
    private_key = models.TextField(verbose_name='Приватний ключ')
    ip_address = models.GenericIPAddressField(verbose_name='IP адреса')
    allowed_ips = models.TextField(
        default='0.0.0.0/0', 
        verbose_name='Дозволені IP'
    )
    
    # Статистика в реальному часі
    bytes_sent = models.BigIntegerField(default=0, verbose_name='Відправлено байт')
    bytes_received = models.BigIntegerField(default=0, verbose_name='Отримано байт')
    last_handshake = models.DateTimeField(blank=True, null=True, verbose_name='Останнє з\'єднання')
    
    # Налаштування peer'а
    keep_alive = models.PositiveIntegerField(blank=True, null=True, verbose_name='Keep Alive')
    is_active = models.BooleanField(default=True, verbose_name='Активний')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'WireGuard Peer'
        verbose_name_plural = 'WireGuard Peer\'и'
        unique_together = ['user', 'server', 'name']
    
    def __str__(self):
        return f"{self.user.username} - {self.name}"
    
    @property
    def is_online(self):
        """Перевірка чи peer онлайн (останній handshake < 3 хвилин)"""
        if not self.last_handshake:
            return False
        return (timezone.now() - self.last_handshake).total_seconds() < 180
    
    @property
    def total_traffic(self):
        """Загальний трафік"""
        return self.bytes_sent + self.bytes_received
    
    def get_sent_mb(self):
        """Відправлено в MB"""
        return round(self.bytes_sent / 1024 / 1024, 2)
    
    def get_received_mb(self):
        """Отримано в MB"""
        return round(self.bytes_received / 1024 / 1024, 2)
    
    def generate_config(self):
        """Генерація конфігураційного файлу"""
        config = f"""[Interface]
PrivateKey = {self.private_key}
Address = {self.ip_address}/32
DNS = {self.server.dns_servers}
MTU = {self.server.mtu}

[Peer]
PublicKey = {self.server.public_key}
Endpoint = {self.server.endpoint}
AllowedIPs = {self.allowed_ips}
"""
        if self.keep_alive or self.server.keep_alive:
            config += f"PersistentKeepalive = {self.keep_alive or self.server.keep_alive}\n"
        
        return config
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wireguard_peers')
    server = models.ForeignKey(WireGuardServer, on_delete=models.CASCADE, related_name='peers')
    public_key = models.TextField(unique=True)
    private_key = models.TextField()
    allowed_ips = models.CharField(max_length=255, default='0.0.0.0/0')
    client_ip = models.GenericIPAddressField()  # IP клієнта у VPN мережі
    preshared_key = models.TextField(blank=True, null=True)
    
    # Налаштування
    persistent_keepalive = models.PositiveIntegerField(default=25)
    is_active = models.BooleanField(default=True)
    
    # Статистика
    last_handshake = models.DateTimeField(blank=True, null=True)
    bytes_sent = models.BigIntegerField(default=0)
    bytes_received = models.BigIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'wireguard_peers'
        verbose_name = 'WireGuard Клієнт'
        verbose_name_plural = 'WireGuard Клієнти'
        unique_together = ['server', 'client_ip']
    
    def __str__(self):
        return f"{self.user.username} - {self.client_ip}"
    
    @property
    def config_content(self):
        """Генерує конфігурацію клієнта"""
        config = f"""[Interface]
PrivateKey = {self.private_key}
Address = {self.client_ip}/32
DNS = {self.server.dns_servers}

[Peer]
PublicKey = {self.server.public_key}
Endpoint = {self.server.endpoint}
AllowedIPs = {self.allowed_ips}
PersistentKeepalive = {self.persistent_keepalive}
"""
        if self.preshared_key:
            config += f"PresharedKey = {self.preshared_key}\n"
        
        return config


class WireGuardConfigTemplate(models.Model):
    """Шаблони конфігурацій для різних типів клієнтів"""
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    allowed_ips = models.CharField(max_length=255, default='0.0.0.0/0')
    dns_servers = models.CharField(max_length=255, default='1.1.1.1,8.8.8.8')
    persistent_keepalive = models.PositiveIntegerField(default=25)
    is_default = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'wireguard_config_templates'
        verbose_name = 'Шаблон Конфігурації'
        verbose_name_plural = 'Шаблони Конфігурацій'
    
    def __str__(self):
        return self.name
