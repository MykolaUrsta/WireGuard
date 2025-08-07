from django.urls import path
from . import views

app_name = 'audit_logging'

urlpatterns = [
    path('', views.user_action_logs, name='audit_list'),
    path('user-actions/', views.user_action_logs, name='user_actions'),
    path('vpn-connections/', views.vpn_connection_logs, name='vpn_connections'),
    path('security-events/', views.security_events, name='security_events'),
    path('api/connection-event/', views.log_connection_event, name='log_connection_event'),
]
