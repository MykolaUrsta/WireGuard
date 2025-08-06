from django.db import models
from accounts.models import CustomUser
from django.utils import timezone


class UserActionLog(models.Model):
    """Модель для логування дій користувачів"""
    
    ACTION_CHOICES = [
        ('login', 'Вхід в систему'),
        ('logout', 'Вихід з системи'),
        ('register', 'Реєстрація'),
        ('2fa_enabled', '2FA увімкнена'),
        ('2fa_disabled', '2FA вимкнена'),
        ('2fa_success', '2FA успішна'),
        ('2fa_failed', '2FA невдала'),
        ('vpn_connected', 'VPN підключено'),
        ('vpn_disconnected', 'VPN відключено'),
        ('vpn_2fa_success', 'VPN 2FA успішна'),
        ('vpn_2fa_failed', 'VPN 2FA невдала'),
        ('user_created', 'Користувач створений'),
        ('user_deleted', 'Користувач видалений'),
        ('user_updated', 'Користувач оновлений'),
        ('wireguard_enabled', 'WireGuard увімкнений'),
        ('wireguard_disabled', 'WireGuard вимкнений'),
        ('config_downloaded', 'Конфігурація завантажена'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='action_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Додаткові поля для VPN з'єднань
    vpn_server_ip = models.GenericIPAddressField(blank=True, null=True)
    vpn_client_ip = models.GenericIPAddressField(blank=True, null=True)
    bytes_transferred = models.BigIntegerField(blank=True, null=True)
    
    class Meta:
        db_table = 'user_action_logs'
        verbose_name = 'Лог дій користувача'
        verbose_name_plural = 'Логи дій користувачів'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
            models.Index(fields=['ip_address', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()} - {self.timestamp}"


class VPNConnectionLog(models.Model):
    """Модель для детального логування VPN підключень"""
    
    CONNECTION_STATUS_CHOICES = [
        ('connecting', 'Підключається'),
        ('connected', 'Підключено'),
        ('disconnecting', 'Відключається'),
        ('disconnected', 'Відключено'),
        ('failed', 'Помилка підключення'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='vpn_connection_logs')
    session_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=CONNECTION_STATUS_CHOICES)
    
    # Інформація про підключення
    client_ip = models.GenericIPAddressField()
    server_ip = models.GenericIPAddressField()
    client_port = models.PositiveIntegerField(blank=True, null=True)
    server_port = models.PositiveIntegerField(default=51820)
    
    # Часові мітки
    connect_time = models.DateTimeField(auto_now_add=True)
    disconnect_time = models.DateTimeField(blank=True, null=True)
    last_seen = models.DateTimeField(auto_now=True)
    
    # Статистика трафіку
    bytes_sent = models.BigIntegerField(default=0)
    bytes_received = models.BigIntegerField(default=0)
    packets_sent = models.BigIntegerField(default=0)
    packets_received = models.BigIntegerField(default=0)
    
    # Додаткова інформація
    client_version = models.CharField(max_length=100, blank=True)
    platform = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        db_table = 'vpn_connection_logs'
        verbose_name = 'Лог VPN підключення'
        verbose_name_plural = 'Логи VPN підключень'
        ordering = ['-connect_time']
        indexes = [
            models.Index(fields=['user', '-connect_time']),
            models.Index(fields=['status', '-connect_time']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.session_id} - {self.get_status_display()}"
    
    @property
    def duration(self):
        """Тривалість підключення"""
        if self.disconnect_time:
            return self.disconnect_time - self.connect_time
        return timezone.now() - self.connect_time
    
    @property
    def total_bytes(self):
        """Загальна кількість переданих байтів"""
        return self.bytes_sent + self.bytes_received


class SecurityEvent(models.Model):
    """Модель для логування подій безпеки"""
    
    EVENT_TYPES = [
        ('auth_failure', 'Невдала автентифікація'),
        ('suspicious_activity', 'Підозріла активність'),
        ('multiple_logins', 'Множинні входи'),
        ('unusual_location', 'Незвичайне розташування'),
        ('brute_force', 'Атака перебору'),
        ('account_locked', 'Акаунт заблокований'),
        ('vpn_abuse', 'Зловживання VPN'),
        ('config_theft', 'Крадіжка конфігурації'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Низька'),
        ('medium', 'Середня'),
        ('high', 'Висока'),
        ('critical', 'Критична'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, blank=True, null=True, related_name='security_events')
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='medium')
    
    description = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    
    # Додаткові дані у форматі JSON
    additional_data = models.JSONField(default=dict, blank=True)
    
    # Статус обробки
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='resolved_security_events')
    resolved_at = models.DateTimeField(blank=True, null=True)
    resolution_notes = models.TextField(blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'security_events'
        verbose_name = 'Подія безпеки'
        verbose_name_plural = 'Події безпеки'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event_type', '-timestamp']),
            models.Index(fields=['severity', '-timestamp']),
            models.Index(fields=['is_resolved', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.get_event_type_display()} - {self.get_severity_display()} - {self.timestamp}"
