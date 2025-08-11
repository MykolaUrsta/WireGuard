from django.urls import path
from . import views

app_name = 'locations'

urlpatterns = [
    # Локації
    path('', views.locations_redirect, name='list'),
    path('list/', views.locations_list, name='actual_list'),
    path('detail/', views.default_location_detail, name='default_detail'),
    path('create/', views.location_create, name='create'),
    path('<int:pk>/', views.location_detail, name='detail'),
    path('<int:pk>/edit/', views.location_edit, name='edit'),
    path('<int:pk>/delete/', views.location_delete, name='delete'),
    
    # Швидке налаштування
    path('quick-setup/', views.quick_setup, name='quick_setup'),
    
    # Мережі
    path('networks/', views.networks_list, name='networks_list'),
    path('networks/create/', views.network_create, name='network_create'),
    path('networks/create/<int:location_pk>/', views.network_create, name='network_create_for_location'),
    path('networks/<int:pk>/', views.network_detail, name='network_detail'),
    
    # Пристрої
    path('devices/', views.my_devices, name='my_devices'),
    path('devices/create/', views.device_create, name='device_create'),
    path('devices/<int:pk>/', views.device_detail, name='device_detail'),
    path('devices/<int:pk>/config/', views.device_config, name='device_config'),
    path('devices/<int:device_id>/download/', views.device_config_download, name='device_config_download'),
    
    # ACL
    path('acl/', views.acl_list, name='acl_list'),
    path('acl/create/', views.acl_create, name='acl_create'),
    path('acl/<int:pk>/', views.acl_detail, name='acl_detail'),
    
    # API endpoints
    path('api/networks/<int:pk>/info/', views.api_network_info, name='api_network_info'),
    path('api/devices/<int:pk>/toggle/', views.api_toggle_device, name='api_toggle_device'),
    path('api/location-stats/<int:pk>/', views.api_location_stats, name='api_location_stats'),
    path('api/location-history/<int:pk>/', views.api_location_history, name='api_location_history'),
    path('api/peer-history/<int:pk>/', views.api_peer_history, name='api_peer_history'),
    path('api/refresh-stats/<int:pk>/', views.api_refresh_location_stats, name='api_refresh_location_stats'),
]
