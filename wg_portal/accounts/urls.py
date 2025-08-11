from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.vpn_overview, name='vpn_overview'),
    path('dashboard/', views.vpn_overview, name='dashboard'),  # Backward compatibility
    path('users/', views.users_list, name='users_list'),
    path('users/add/', views.user_add, name='user_add'),
    path('users/<int:pk>/', views.user_detail, name='user_detail'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:pk>/delete/', views.user_delete, name='user_delete'),
    path('users/<int:pk>/toggle/', views.user_toggle_active, name='user_toggle_active'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.RegistrationView.as_view(), name='register'),
    path('verify-2fa/', views.Verify2FAView.as_view(), name='verify_2fa'),
    path('setup-2fa/', views.setup_2fa, name='setup_2fa'),
    path('disable-2fa/', views.disable_2fa, name='disable_2fa'),
    
    # API endpoints for VPN authentication
    path('api/vpn/auth/', views.vpn_auth_check, name='vpn_auth_check'),
    path('api/vpn/2fa/', views.vpn_2fa_verify, name='vpn_2fa_verify'),
    
    # API endpoints for real-time data
    path('api/connected-users/', views.connected_users_api, name='connected_users_api'),
    path('api/device/<int:device_id>/config/', views.device_config_modal, name='device_config_modal'),
    path('api/device/<int:device_id>/delete/', views.device_delete, name='device_delete'),
    path('api/user/<int:user_id>/devices/', views.user_devices_api, name='user_devices_api'),
]
