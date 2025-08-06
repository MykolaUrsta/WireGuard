from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.plugins.otp_totp.admin import TOTPDeviceAdmin
from .models import CustomUser, VPNSession

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_wireguard_enabled', 'is_2fa_enabled', 'last_vpn_connection')
    list_filter = ('is_staff', 'is_active', 'is_wireguard_enabled', 'is_2fa_enabled', 'created_at')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-created_at',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('WireGuard Settings', {
            'fields': ('is_wireguard_enabled', 'wireguard_ip', 'wireguard_public_key')
        }),
        ('Security Settings', {
            'fields': ('is_2fa_enabled', 'last_vpn_connection')
        }),
    )
    
    readonly_fields = ('wireguard_public_key', 'last_login', 'date_joined', 'created_at', 'updated_at')

@admin.register(VPNSession)
class VPNSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'client_ip', 'server_ip', 'start_time', 'end_time', 'is_active', 'duration')
    list_filter = ('is_active', 'start_time', 'server_ip')
    search_fields = ('user__username', 'user__email', 'client_ip')
    readonly_fields = ('start_time', 'duration')
    ordering = ('-start_time',)
    
    def duration(self, obj):
        return obj.duration
    duration.short_description = 'Тривалість'
