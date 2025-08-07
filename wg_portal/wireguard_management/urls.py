from django.urls import path
from . import views

app_name = 'wireguard_management'

urlpatterns = [
    path('api/location-history/<int:pk>/', views.api_location_history, name='api_location_history'),
    path('api/peer-history/<int:pk>/', views.api_peer_history, name='api_peer_history'),
    # Networks
    path('networks/', views.networks_list, name='networks'),
    path('networks/create/', views.network_create, name='create_network'),
    path('networks/<int:pk>/', views.network_detail, name='network_detail'),
    path('networks/<int:pk>/edit/', views.network_edit, name='network_edit'),
    path('networks/<int:pk>/delete/', views.network_delete, name='network_delete'),
    
    # Devices
    path('devices/', views.devices_list, name='devices'),
    path('devices/create/', views.device_create, name='device_create'),
    path('devices/<int:pk>/', views.device_detail, name='device_detail'),
    path('devices/<int:pk>/edit/', views.device_edit, name='device_edit'),
    path('devices/<int:pk>/config/', views.device_config, name='device_config'),
    path('devices/<int:pk>/qr/', views.device_qr_code, name='device_qr'),
    path('devices/<int:pk>/delete/', views.device_delete, name='device_delete'),
    
    # WireGuard Tunnels
    path('tunnels/', views.tunnels_list, name='tunnels'),
    path('tunnels/create/', views.tunnel_create, name='tunnel_create'),
    path('tunnels/<int:pk>/', views.tunnel_detail, name='tunnel_detail'),
    path('tunnels/<int:pk>/start/', views.tunnel_start, name='tunnel_start'),
    path('tunnels/<int:pk>/stop/', views.tunnel_stop, name='tunnel_stop'),
    path('tunnels/<int:pk>/restart/', views.tunnel_restart, name='tunnel_restart'),
    path('tunnels/<int:pk>/config/', views.tunnel_config, name='tunnel_config'),
    path('tunnels/<int:pk>/delete/', views.tunnel_delete, name='tunnel_delete'),
    
    # ACL Rules & Firewall
    path('networks/<int:network_pk>/acl/', views.acl_rules, name='acl_rules'),
    path('networks/<int:network_pk>/acl/create/', views.acl_rule_create, name='acl_rule_create'),
    path('acl/<int:pk>/edit/', views.acl_rule_edit, name='acl_rule_edit'),
    path('acl/<int:pk>/delete/', views.acl_rule_delete, name='acl_rule_delete'),
    
    # Firewall Rules
    path('firewall/', views.firewall_rules, name='firewall_rules'),
    path('firewall/create/', views.firewall_rule_create, name='firewall_rule_create'),
    path('firewall/<int:pk>/edit/', views.firewall_rule_edit, name='firewall_rule_edit'),
    path('firewall/<int:pk>/delete/', views.firewall_rule_delete, name='firewall_rule_delete'),
    path('firewall/<int:pk>/toggle/', views.firewall_rule_toggle, name='firewall_rule_toggle'),
    
    # TOTP & Security
    path('devices/<int:pk>/totp/setup/', views.device_totp_setup, name='device_totp_setup'),
    path('devices/<int:pk>/totp/verify/', views.device_totp_verify, name='device_totp_verify'),
    path('devices/<int:pk>/totp/disable/', views.device_totp_disable, name='device_totp_disable'),
    path('totp/qr/<str:secret>/', views.totp_qr_code, name='totp_qr_code'),
    
    # Device Groups
    path('groups/', views.device_groups, name='device_groups'),
    path('groups/create/', views.device_group_create, name='device_group_create'),
    path('groups/<int:pk>/edit/', views.device_group_edit, name='device_group_edit'),
    path('groups/<int:pk>/delete/', views.device_group_delete, name='device_group_delete'),
    
    # API для моніторингу
    path('api/network-status/', views.api_network_status, name='api_network_status'),
    path('api/device-stats/<int:pk>/', views.api_device_stats, name='api_device_stats'),
    path('api/tunnel-status/<int:pk>/', views.api_tunnel_status, name='api_tunnel_status'),
    path('api/firewall-status/', views.api_firewall_status, name='api_firewall_status'),
    
    # Legacy URLs (для зворотної сумісності)
    path('create-config/', views.create_config, name='create_config'),
    path('delete-config/', views.delete_config, name='delete_config'),
    path('download-config/', views.download_config, name='download_config'),
    path('stats/', views.connection_stats, name='connection_stats'),
    path('qr-code/', views.get_qr_code, name='qr_code'),
]
