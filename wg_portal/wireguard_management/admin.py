from django.contrib import admin
from django.utils.html import format_html
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.safestring import mark_safe
from .models import WireGuardNetwork, WireGuardServer, WireGuardPeer
import subprocess
import json


@admin.register(WireGuardNetwork)
class WireGuardNetworkAdmin(admin.ModelAdmin):
    """Адмін панель для WireGuard мереж"""
    
    list_display = ['name', 'network_cidr', 'peer_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'network_cidr', 'description']
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        """Тільки суперкористувачі можуть керувати мережами"""
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.none()
        return qs
    
    def has_add_permission(self, request):
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def peer_count(self, obj):
        """Кількість peer'ів в мережі"""
        if hasattr(obj, 'server'):
            count = obj.server.peers.count()
            active_count = obj.server.peers.filter(is_active=True).count()
            return format_html(
                '<span style="color: blue;">{} всього</span><br/>'
                '<span style="color: green;">{} активних</span>',
                count, active_count
            )
        return "Немає сервера"
    peer_count.short_description = 'Peer\'и'


@admin.register(WireGuardServer)
class WireGuardServerAdmin(admin.ModelAdmin):
    """Адмін панель для WireGuard серверів"""
    
    list_display = [
        'name', 'network', 'endpoint', 'listen_port', 
        'peer_stats', 'server_status', 'is_active'
    ]
    list_filter = ['is_active', 'network', 'created_at']
    search_fields = ['name', 'endpoint', 'network__name']
    readonly_fields = ['created_at', 'updated_at', 'total_peers', 'active_peers']
    
    fieldsets = (
        ('Основні налаштування', {
            'fields': ('name', 'network', 'endpoint', 'listen_port')
        }),
        ('Ключі шифрування', {
            'fields': ('public_key', 'private_key'),
            'classes': ['collapse']
        }),
        ('Мережні налаштування', {
            'fields': ('server_ip', 'dns_servers', 'keep_alive', 'mtu')
        }),
        ('Статистика', {
            'fields': ('total_peers', 'active_peers', 'is_active'),
            'classes': ['collapse']
        }),
        ('Системна інформація', {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        }),
    )
    
    def get_queryset(self, request):
        """Тільки суперкористувачі можуть керувати серверами"""
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.none()
        return qs
    
    def has_add_permission(self, request):
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def peer_stats(self, obj):
        """Статистика peer'ів"""
        total = obj.total_peers
        active = obj.active_peers
        offline = total - active
        
        return format_html(
            '<div style="text-align: center;">'
            '<span style="color: green; font-weight: bold;">{}</span> активних<br/>'
            '<span style="color: red;">{}</span> офлайн<br/>'
            '<span style="color: blue;">{}</span> всього'
            '</div>',
            active, offline, total
        )
    peer_stats.short_description = 'Статистика'
    
    def server_status(self, obj):
        """Статус сервера"""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">●</span> Активний'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">●</span> Неактивний'
        )
    server_status.short_description = 'Статус'
    
    actions = ['generate_server_config', 'update_peer_stats']
    
    def generate_server_config(self, request, queryset):
        """Генерація конфігурації сервера"""
        if not request.user.is_superuser:
            self.message_user(request, "Недостатньо прав", level='error')
            return
        
        for server in queryset:
            # Тут може бути логіка генерації конфігурації
            pass
        
        self.message_user(request, "Конфігурацію згенеровано", level='success')
    generate_server_config.short_description = 'Генерувати конфігурацію сервера'
    
    def update_peer_stats(self, request, queryset):
        """Оновити статистику peer'ів"""
        if not request.user.is_superuser:
            self.message_user(request, "Недостатньо прав", level='error')
            return
        
        for server in queryset:
            server.update_peer_counts()
        
        self.message_user(request, "Статистику оновлено", level='success')
    update_peer_stats.short_description = 'Оновити статистику'


@admin.register(WireGuardPeer)
class WireGuardPeerAdmin(admin.ModelAdmin):
    """Адмін панель для WireGuard peer'ів"""
    
    list_display = [
        'user', 'name', 'server', 'ip_address', 
        'connection_status', 'traffic_stats', 'is_active'
    ]
    list_filter = [
        'is_active', 'server', 'server__network', 
        'last_handshake', 'created_at'
    ]
    search_fields = [
        'user__username', 'user__email', 'name', 'ip_address'
    ]
    readonly_fields = [
        'bytes_sent', 'bytes_received', 'last_handshake', 
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Основна інформація', {
            'fields': ('user', 'server', 'name', 'is_active')
        }),
        ('Мережні налаштування', {
            'fields': ('ip_address', 'allowed_ips', 'keep_alive')
        }),
        ('Ключі шифрування', {
            'fields': ('public_key', 'private_key'),
            'classes': ['collapse']
        }),
        ('Статистика трафіку', {
            'fields': ('bytes_sent', 'bytes_received', 'last_handshake'),
            'classes': ['collapse']
        }),
        ('Системна інформація', {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        }),
    )
    
    def get_queryset(self, request):
        """Суперкористувачі бачать всіх, інші - тільки свої peer'и"""
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(user=request.user)
        return qs
    
    def has_add_permission(self, request):
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj and obj.user == request.user:
            return True
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def connection_status(self, obj):
        """Статус з'єднання"""
        if obj.is_online:
            return format_html(
                '<span style="color: green; font-weight: bold;">●</span> Онлайн<br/>'
                '<small>Останнє: {}</small>',
                obj.last_handshake.strftime('%H:%M:%S') if obj.last_handshake else 'Ніколи'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">●</span> Офлайн<br/>'
            '<small>Останнє: {}</small>',
            obj.last_handshake.strftime('%d.%m %H:%M') if obj.last_handshake else 'Ніколи'
        )
    connection_status.short_description = 'З\'єднання'
    
    def traffic_stats(self, obj):
        """Статистика трафіку"""
        sent_mb = obj.get_sent_mb()
        received_mb = obj.get_received_mb()
        total_mb = sent_mb + received_mb
        
        # Колір залежно від обсягу
        if total_mb > 1000:  # > 1GB
            color = 'red'
        elif total_mb > 100:  # > 100MB
            color = 'orange'
        else:
            color = 'green'
        
        return format_html(
            '<div style="color: {}; text-align: center;">'
            '↑ {:.1f} MB<br/>'
            '↓ {:.1f} MB<br/>'
            '<strong>{:.1f} MB</strong>'
            '</div>',
            color, sent_mb, received_mb, total_mb
        )
    traffic_stats.short_description = 'Трафік'
    
    # Дії для peer'ів
    actions = ['enable_peers', 'disable_peers', 'reset_traffic', 'download_config']
    
    def enable_peers(self, request, queryset):
        """Увімкнути peer'и"""
        if not request.user.is_superuser:
            self.message_user(request, "Недостатньо прав", level='error')
            return
        
        updated = queryset.update(is_active=True)
        self.message_user(
            request, 
            f'Увімкнено {updated} peer(ів)',
            level='success'
        )
    enable_peers.short_description = 'Увімкнути peer\'и'
    
    def disable_peers(self, request, queryset):
        """Вимкнути peer'и"""
        if not request.user.is_superuser:
            self.message_user(request, "Недостатньо прав", level='error')
            return
        
        updated = queryset.update(is_active=False)
        self.message_user(
            request, 
            f'Вимкнено {updated} peer(ів)',
            level='success'
        )
    disable_peers.short_description = 'Вимкнути peer\'и'
    
    def reset_traffic(self, request, queryset):
        """Скинути статистику трафіку"""
        if not request.user.is_superuser:
            self.message_user(request, "Недостатньо прав", level='error')
            return
        
        updated = queryset.update(bytes_sent=0, bytes_received=0)
        self.message_user(
            request, 
            f'Статистику скинуто для {updated} peer(ів)',
            level='success'
        )
    reset_traffic.short_description = 'Скинути статистику'
    
    def download_config(self, request, queryset):
        """Завантажити конфігурацію"""
        # Ця функція буде реалізована пізніше
        pass
    download_config.short_description = 'Завантажити конфігурацію'
