from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Q
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Розширена адмін панель для користувачів"""
    
    # Поля для відображення в списку
    list_display = [
        'username', 'email', 'get_full_name_display', 'department', 
        'is_wireguard_enabled', 'online_status', 'traffic_display', 
        'last_vpn_connection', 'is_active', 'is_staff'
    ]
    
    list_filter = [
        'is_active', 'is_staff', 'is_superuser', 'is_wireguard_enabled',
        'is_online', 'department', 'date_joined'
    ]
    
    search_fields = ['username', 'email', 'first_name', 'last_name', 'department']
    
    # Фільтри для швидкого пошуку
    list_per_page = 25
    
    # Поля для редагування
    fieldsets = (
        ('Основна інформація', {
            'fields': ('username', 'email', 'first_name', 'last_name', 'avatar')
        }),
        ('Контактна інформація', {
            'fields': ('phone', 'department', 'position')
        }),
        ('WireGuard налаштування', {
            'fields': (
                'is_wireguard_enabled', 'wireguard_public_key', 'wireguard_private_key',
                'wireguard_ip', 'allowed_ips', 'data_limit'
            ),
            'classes': ['collapse']
        }),
        ('Статистика трафіку', {
            'fields': (
                'total_upload', 'total_download', 'last_handshake', 
                'is_online', 'last_vpn_connection'
            ),
            'classes': ['collapse']
        }),
        ('Безпека', {
            'fields': ('is_2fa_enabled', 'backup_codes'),
            'classes': ['collapse']
        }),
        ('Права доступу', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ['collapse']
        }),
        ('Важливі дати', {
            'fields': ('last_login', 'date_joined'),
            'classes': ['collapse']
        }),
    )
    
    # Поля тільки для читання
    readonly_fields = [
        'date_joined', 'last_login', 'total_upload', 'total_download',
        'last_handshake', 'is_online', 'last_vpn_connection'
    ]
    
    def get_queryset(self, request):
        """Обмеження доступу - тільки суперкористувачі можуть бачити всіх користувачів"""
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            # Звичайний staff може бачити тільки себе
            return qs.filter(id=request.user.id)
        return qs
    
    def has_add_permission(self, request):
        """Тільки суперкористувачі можуть створювати користувачів"""
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """Суперкористувачі можуть редагувати всіх, інші - тільки себе"""
        if request.user.is_superuser:
            return True
        if obj and obj.id == request.user.id:
            return True
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Тільки суперкористувачі можуть видаляти користувачів"""
        return request.user.is_superuser
    
    def get_full_name_display(self, obj):
        """Відображення повного імені"""
        full_name = obj.get_full_name()
        return full_name if full_name else obj.username
    get_full_name_display.short_description = 'Повне ім\'я'
    
    def online_status(self, obj):
        """Статус онлайн"""
        if obj.is_online:
            return format_html(
                '<span style="color: green;">●</span> Онлайн'
            )
        return format_html(
            '<span style="color: red;">●</span> Офлайн'
        )
    online_status.short_description = 'Статус'
    
    def traffic_display(self, obj):
        """Відображення трафіку"""
        upload_mb = obj.get_upload_mb()
        download_mb = obj.get_download_mb()
        total_mb = upload_mb + download_mb
        
        # Колір залежно від використання
        color = 'green'
        if obj.data_limit:
            usage_percent = obj.traffic_usage_percent
            if usage_percent > 80:
                color = 'red'
            elif usage_percent > 60:
                color = 'orange'
        
        return format_html(
            '<span style="color: {};">↑{:.1f} MB / ↓{:.1f} MB<br/>Всього: {:.1f} MB</span>',
            color, upload_mb, download_mb, total_mb
        )
    traffic_display.short_description = 'Трафік'
    
    # Дії для вибраних користувачів
    actions = ['enable_wireguard', 'disable_wireguard', 'reset_traffic_stats']
    
    def enable_wireguard(self, request, queryset):
        """Увімкнути WireGuard для вибраних користувачів"""
        if not request.user.is_superuser:
            self.message_user(request, "Недостатньо прав", level='error')
            return
        
        updated = queryset.update(is_wireguard_enabled=True)
        self.message_user(
            request, 
            f'WireGuard увімкнено для {updated} користувач(ів)',
            level='success'
        )
    enable_wireguard.short_description = 'Увімкнути WireGuard'
    
    def disable_wireguard(self, request, queryset):
        """Вимкнути WireGuard для вибраних користувачів"""
        if not request.user.is_superuser:
            self.message_user(request, "Недостатньо прав", level='error')
            return
        
        updated = queryset.update(is_wireguard_enabled=False)
        self.message_user(
            request, 
            f'WireGuard вимкнено для {updated} користувач(ів)',
            level='success'
        )
    disable_wireguard.short_description = 'Вимкнути WireGuard'
    
    def reset_traffic_stats(self, request, queryset):
        """Скинути статистику трафіку"""
        if not request.user.is_superuser:
            self.message_user(request, "Недостатньо прав", level='error')
            return
        
        updated = queryset.update(total_upload=0, total_download=0)
        self.message_user(
            request, 
            f'Статистику скинуто для {updated} користувач(ів)',
            level='success'
        )
    reset_traffic_stats.short_description = 'Скинути статистику трафіку'


# Приховуємо стандартні моделі Django OTP від звичайних користувачів
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.plugins.otp_static.models import StaticDevice

admin.site.unregister(TOTPDevice)
admin.site.unregister(StaticDevice)

# Реєструємо їх тільки для суперкористувачів
class RestrictedTOTPDeviceAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser

class RestrictedStaticDeviceAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser

admin.site.register(TOTPDevice, RestrictedTOTPDeviceAdmin)
admin.site.register(StaticDevice, RestrictedStaticDeviceAdmin)
