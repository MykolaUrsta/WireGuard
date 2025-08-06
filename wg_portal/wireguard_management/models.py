from django.db import models
from accounts.models import CustomUser


class WireGuardServer(models.Model):
    """Модель WireGuard сервера"""
    
    name = models.CharField(max_length=100, unique=True)
    public_key = models.TextField()
    private_key = models.TextField()
    endpoint = models.CharField(max_length=255)  # IP:PORT
    listen_port = models.PositiveIntegerField(default=51820)
    network = models.CharField(max_length=18, default='10.13.13.0/24')  # CIDR
    dns_servers = models.CharField(max_length=255, default='1.1.1.1,8.8.8.8')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'wireguard_servers'
        verbose_name = 'WireGuard Сервер'
        verbose_name_plural = 'WireGuard Сервери'
    
    def __str__(self):
        return self.name


class WireGuardPeer(models.Model):
    """Модель клієнта WireGuard (peer)"""
    
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='wireguard_peer')
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
