from django.urls import path
from . import views

app_name = 'wireguard_management'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('create-config/', views.create_config, name='create_config'),
    path('delete-config/', views.delete_config, name='delete_config'),
    path('download-config/', views.download_config, name='download_config'),
    path('stats/', views.connection_stats, name='connection_stats'),
    path('qr-code/', views.get_qr_code, name='qr_code'),
]
