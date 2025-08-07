from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.vpn_overview, name='vpn_overview'),
    path('dashboard/', views.vpn_overview, name='dashboard'),  # Backward compatibility
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.RegistrationView.as_view(), name='register'),
    path('verify-2fa/', views.Verify2FAView.as_view(), name='verify_2fa'),
    path('setup-2fa/', views.setup_2fa, name='setup_2fa'),
    path('disable-2fa/', views.disable_2fa, name='disable_2fa'),
    
    # API endpoints for VPN authentication
    path('api/vpn/auth/', views.vpn_auth_check, name='vpn_auth_check'),
    path('api/vpn/2fa/', views.vpn_2fa_verify, name='vpn_2fa_verify'),
]
