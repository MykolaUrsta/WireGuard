from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import RegexValidator

class CustomUser(AbstractUser):
    """Розширена модель користувача з додатковими полями для WireGuard"""
    
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    # WireGuard базові поля
    is_wireguard_enabled = models.BooleanField(default=False)
    wireguard_public_key = models.TextField(blank=True, null=True)
    wireguard_private_key = models.TextField(blank=True, null=True)
    wireguard_ip = models.GenericIPAddressField(blank=True, null=True)
    
    # Статистика трафіку
    total_upload = models.BigIntegerField(default=0, help_text='Загальний upload в байтах')
    total_download = models.BigIntegerField(default=0, help_text='Загальний download в байтах')
    last_handshake = models.DateTimeField(blank=True, null=True, help_text='Останнє з\'єднання')
    is_online = models.BooleanField(default=False, help_text='Онлайн статус')
    
    # Обмеження
    data_limit = models.BigIntegerField(blank=True, null=True, help_text='Ліміт трафіку в байтах')
    allowed_ips = models.TextField(default='0.0.0.0/0, ::/0', help_text='Дозволені IP')
    
    # Профіль користувача
    department = models.CharField(max_length=100, blank=True, null=True)
    position = models.CharField(max_length=100, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    
    # 2FA fields
    is_2fa_enabled = models.BooleanField(default=False)
    backup_codes = models.JSONField(default=list, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_vpn_connection = models.DateTimeField(blank=True, null=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    @property
    def total_traffic(self):
        """Загальний трафік"""
        return self.total_upload + self.total_download
    
    @property
    def traffic_usage_percent(self):
        """Відсоток використання трафіку"""
        if self.data_limit:
            return min((self.total_traffic / self.data_limit) * 100, 100)
        return 0
    
    def get_upload_mb(self):
        """Upload в MB"""
        return round(self.total_upload / 1024 / 1024, 2)
    
    def get_download_mb(self):
        """Download в MB"""
        return round(self.total_download / 1024 / 1024, 2)
    
    class Meta:
        db_table = 'auth_user'
        verbose_name = 'Користувач'
        verbose_name_plural = 'Користувачі'
    
    def __str__(self):
        return f"{self.username} ({self.email})"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class VPNSession(models.Model):
    """Модель для відстеження сесій VPN підключень"""
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='vpn_sessions')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(blank=True, null=True)
    client_ip = models.GenericIPAddressField()
    server_ip = models.GenericIPAddressField()
    bytes_sent = models.BigIntegerField(default=0)
    bytes_received = models.BigIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'vpn_sessions'
        verbose_name = 'VPN Сесія'
        verbose_name_plural = 'VPN Сесії'
        ordering = ['-start_time']
    
    def __str__(self):
        return f"{self.user.username} - {self.start_time}"
    
    @property
    def duration(self):
        if self.end_time:
            return self.end_time - self.start_time
        return timezone.now() - self.start_time
