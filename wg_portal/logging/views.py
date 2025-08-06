from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from .models import UserActionLog, VPNConnectionLog, SecurityEvent
import json
import logging

logger = logging.getLogger(__name__)

@login_required
def logs_dashboard(request):
    """Панель логів та статистики"""
    context = {
        'total_actions': UserActionLog.objects.count(),
        'total_vpn_connections': VPNConnectionLog.objects.count(),
        'total_security_events': SecurityEvent.objects.count(),
        'recent_actions': UserActionLog.objects.filter(user=request.user)[:10],
    }
    return render(request, 'logging_app/dashboard.html', context)

@login_required
def user_action_logs(request):
    """Логи дій користувачів"""
    logs = UserActionLog.objects.filter(user=request.user).order_by('-timestamp')
    
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'logs': page_obj.object_list,
    }
    return render(request, 'logging_app/user_actions.html', context)

@login_required
def vpn_connection_logs(request):
    """Логи VPN підключень"""
    logs = VPNConnectionLog.objects.filter(user=request.user).order_by('-connect_time')
    
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'logs': page_obj.object_list,
    }
    return render(request, 'logging_app/vpn_connections.html', context)

@login_required
def security_events(request):
    """Події безпеки"""
    if not request.user.is_staff:
        return render(request, 'logging_app/access_denied.html')
    
    events = SecurityEvent.objects.all().order_by('-timestamp')
    
    paginator = Paginator(events, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'events': page_obj.object_list,
    }
    return render(request, 'logging_app/security_events.html', context)

@csrf_exempt
@require_http_methods(["POST"])
def log_connection_event(request):
    """API endpoint для логування подій підключення"""
    try:
        data = json.loads(request.body)
        event_type = data.get('event_type')
        client_public_key = data.get('client_public_key')
        client_ip = data.get('client_ip')
        timestamp = data.get('timestamp')
        
        logger.info(f"VPN connection event: {event_type} from {client_ip}")
        
        # Тут можна додати логіку для обробки подій
        # Наприклад, знайти користувача за публічним ключем
        # та створити відповідний лог
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Error logging connection event: {e}")
        return JsonResponse({'success': False, 'error': str(e)})
