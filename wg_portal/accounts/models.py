from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class CustomUser(AbstractUser):
    """Розширена модель користувача з додатковими полями для WireGuard"""
    
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    is_wireguard_enabled = models.BooleanField(default=False)
    wireguard_public_key = models.TextField(blank=True, null=True)
    wireguard_private_key = models.TextField(blank=True, null=True)
    wireguard_ip = models.GenericIPAddressField(blank=True, null=True)
    wireguard_config = models.TextField(blank=True, null=True)
    
    # 2FA fields
    is_2fa_enabled = models.BooleanField(default=False)
    backup_codes = models.JSONField(default=list, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_vpn_connection = models.DateTimeField(blank=True, null=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
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
