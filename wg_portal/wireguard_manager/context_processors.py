from django.contrib.auth import get_user_model
from wireguard_management.models import WireGuardNetwork, WireGuardPeer

User = get_user_model()

def admin_dashboard_stats(request):
    """Context processor для статистики admin dashboard"""
    
    if not request.path.startswith('/admin/'):
        return {}
    
    # Базова статистика
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    total_networks = WireGuardNetwork.objects.count()
    
    # Розрахунок загального трафіку
    total_traffic_bytes = sum([
        user.total_upload + user.total_download 
        for user in User.objects.all()
    ])
    total_traffic_gb = round(total_traffic_bytes / (1024**3), 2)
    
    return {
        'total_users': total_users,
        'active_users': active_users,
        'total_networks': total_networks,
        'total_traffic_gb': total_traffic_gb,
    }
