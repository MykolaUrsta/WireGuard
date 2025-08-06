from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from .utils import WireGuardManager
from .models import WireGuardPeer
from logging_app.models import UserActionLog
import json
import logging

logger = logging.getLogger(__name__)

@login_required
def dashboard(request):
    """Панель управління WireGuard"""
    context = {
        'user': request.user,
        'has_wireguard': hasattr(request.user, 'wireguard_peer'),
    }
    
    if hasattr(request.user, 'wireguard_peer'):
        peer = request.user.wireguard_peer
        context.update({
            'peer': peer,
            'config': peer.config_content,
            'last_handshake': peer.last_handshake,
            'bytes_sent': peer.bytes_sent,
            'bytes_received': peer.bytes_received,
        })
    
    return render(request, 'wireguard_management/dashboard.html', context)

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def create_config(request):
    """Створює конфігурацію WireGuard для користувача"""
    try:
        if hasattr(request.user, 'wireguard_peer'):
            return JsonResponse({'success': False, 'message': 'Конфігурація вже існує'})
        
        wg_manager = WireGuardManager()
        peer = wg_manager.create_peer(request.user)
        
        UserActionLog.objects.create(
            user=request.user,
            action='wireguard_enabled',
            ip_address=request.META.get('REMOTE_ADDR'),
            description=f'WireGuard конфігурація створена, IP: {peer.client_ip}'
        )
        
        return JsonResponse({
            'success': True, 
            'message': 'Конфігурація WireGuard створена',
            'client_ip': peer.client_ip
        })
        
    except Exception as e:
        logger.error(f"Помилка створення WireGuard конфігурації: {e}")
        return JsonResponse({'success': False, 'message': str(e)})

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def delete_config(request):
    """Видаляє конфігурацію WireGuard користувача"""
    try:
        if not hasattr(request.user, 'wireguard_peer'):
            return JsonResponse({'success': False, 'message': 'Конфігурація не існує'})
        
        wg_manager = WireGuardManager()
        wg_manager.delete_peer(request.user)
        
        UserActionLog.objects.create(
            user=request.user,
            action='wireguard_disabled',
            ip_address=request.META.get('REMOTE_ADDR'),
            description='WireGuard конфігурація видалена'
        )
        
        return JsonResponse({'success': True, 'message': 'Конфігурація WireGuard видалена'})
        
    except Exception as e:
        logger.error(f"Помилка видалення WireGuard конфігурації: {e}")
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
def download_config(request):
    """Завантажує файл конфігурації WireGuard"""
    if not hasattr(request.user, 'wireguard_peer'):
        messages.error(request, 'Конфігурація WireGuard не створена')
        return redirect('accounts:dashboard')
    
    peer = request.user.wireguard_peer
    config_content = peer.config_content
    
    UserActionLog.objects.create(
        user=request.user,
        action='config_downloaded',
        ip_address=request.META.get('REMOTE_ADDR'),
        description='Файл конфігурації WireGuard завантажено'
    )
    
    response = HttpResponse(config_content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{request.user.username}_wireguard.conf"'
    return response

@login_required
def connection_stats(request):
    """Статистика підключень користувача"""
    if not hasattr(request.user, 'wireguard_peer'):
        return JsonResponse({'error': 'Конфігурація не створена'})
    
    peer = request.user.wireguard_peer
    
    # Оновлюємо статистику
    wg_manager = WireGuardManager()
    wg_manager.get_peer_statistics(peer)
    
    # Перезавантажуємо peer з бази даних
    peer.refresh_from_db()
    
    stats = {
        'client_ip': peer.client_ip,
        'last_handshake': peer.last_handshake.isoformat() if peer.last_handshake else None,
        'bytes_sent': peer.bytes_sent,
        'bytes_received': peer.bytes_received,
        'total_bytes': peer.bytes_sent + peer.bytes_received,
        'is_connected': wg_manager.is_peer_connected(peer),
    }
    
    return JsonResponse(stats)
