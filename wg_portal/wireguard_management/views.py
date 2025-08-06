from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .models import WireGuardNetwork, WireGuardServer, WireGuardPeer
from .utils import generate_wireguard_config, update_server_config
from accounts.models import CustomUser
import subprocess
import json
import qrcode
import io
import base64


@login_required
def dashboard(request):
    """Dashboard з статистикою WireGuard"""
    
    # Статистика для поточного користувача
    user_peers = WireGuardPeer.objects.filter(user=request.user)
    
    context = {
        'user_peers': user_peers,
        'total_networks': WireGuardNetwork.objects.filter(is_active=True).count(),
        'active_servers': WireGuardServer.objects.filter(is_active=True).count(),
    }
    
    # Додаткова статистика для суперкористувачів
    if request.user.is_superuser:
        context.update({
            'all_peers': WireGuardPeer.objects.all()[:10],  # Останні 10 peer'ів
            'total_traffic': sum([
                user.total_upload + user.total_download 
                for user in CustomUser.objects.all()
            ]),
        })
    
    return render(request, 'wireguard_management/dashboard.html', context)


@login_required
def create_config(request):
    """Створення нової конфігурації WireGuard"""
    
    if request.method == 'POST':
        try:
            # Отримуємо дані з форми
            server_id = request.POST.get('server_id')
            peer_name = request.POST.get('peer_name', f"{request.user.username}_device")
            
            server = get_object_or_404(WireGuardServer, id=server_id)
            
            # Перевіряємо права доступу
            if not request.user.is_superuser and server.network.is_active is False:
                messages.error(request, "Немає доступу до цієї мережі")
                return redirect('wireguard_management:dashboard')
            
            # Генеруємо ключі
            private_key = subprocess.check_output(['wg', 'genkey'], text=True).strip()
            public_key = subprocess.check_output(['wg', 'pubkey'], input=private_key, text=True).strip()
            
            # Отримуємо доступний IP
            peer_ip = server.network.get_next_available_ip()
            if not peer_ip:
                messages.error(request, "Немає доступних IP адрес в мережі")
                return redirect('wireguard_management:dashboard')
            
            # Створюємо peer
            peer = WireGuardPeer.objects.create(
                user=request.user,
                server=server,
                name=peer_name,
                public_key=public_key,
                private_key=private_key,
                ip_address=peer_ip,
                is_active=True
            )
            
            # Оновлюємо користувача
            request.user.is_wireguard_enabled = True
            request.user.wireguard_public_key = public_key
            request.user.wireguard_private_key = private_key
            request.user.wireguard_ip = peer_ip
            request.user.save()
            
            # Оновлюємо конфігурацію сервера
            update_server_config(server)
            
            messages.success(request, f"Конфігурацію '{peer_name}' створено успішно!")
            return redirect('wireguard_management:dashboard')
            
        except Exception as e:
            messages.error(request, f"Помилка створення конфігурації: {str(e)}")
            return redirect('wireguard_management:dashboard')
    
    # GET запит - показуємо форму
    available_servers = WireGuardServer.objects.filter(is_active=True)
    if not request.user.is_superuser:
        available_servers = available_servers.filter(network__is_active=True)
    
    return render(request, 'wireguard_management/create_config.html', {
        'available_servers': available_servers
    })


@login_required
def download_config(request):
    """Завантаження конфігурації WireGuard"""
    
    peer_id = request.GET.get('peer_id')
    if not peer_id:
        messages.error(request, "Не вказано ID peer'а")
        return redirect('wireguard_management:dashboard')
    
    try:
        peer = get_object_or_404(WireGuardPeer, id=peer_id)
        
        # Перевіряємо права доступу
        if not request.user.is_superuser and peer.user != request.user:
            messages.error(request, "Немає доступу до цієї конфігурації")
            return redirect('wireguard_management:dashboard')
        
        # Генеруємо конфігурацію
        config_content = generate_wireguard_config(peer)
        
        # Повертаємо файл
        response = HttpResponse(config_content, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{peer.name}.conf"'
        return response
        
    except Exception as e:
        messages.error(request, f"Помилка завантаження конфігурації: {str(e)}")
        return redirect('wireguard_management:dashboard')


@login_required
def delete_config(request):
    """Видалення конфігурації WireGuard"""
    
    if request.method == 'POST':
        peer_id = request.POST.get('peer_id')
        
        try:
            peer = get_object_or_404(WireGuardPeer, id=peer_id)
            
            # Перевіряємо права доступу
            if not request.user.is_superuser and peer.user != request.user:
                messages.error(request, "Немає доступу до цієї конфігурації")
                return redirect('wireguard_management:dashboard')
            
            peer_name = peer.name
            server = peer.server
            
            # Видаляємо peer
            peer.delete()
            
            # Оновлюємо конфігурацію сервера
            update_server_config(server)
            
            messages.success(request, f"Конфігурацію '{peer_name}' видалено успішно!")
            
        except Exception as e:
            messages.error(request, f"Помилка видалення конфігурації: {str(e)}")
    
    return redirect('wireguard_management:dashboard')


@login_required
def connection_stats(request):
    """API для отримання статистики підключень"""
    
    if request.method == 'GET':
        user_peers = WireGuardPeer.objects.filter(user=request.user)
        
        stats = []
        for peer in user_peers:
            stats.append({
                'id': peer.id,
                'name': peer.name,
                'ip_address': peer.ip_address,
                'is_online': peer.is_online,
                'last_handshake': peer.last_handshake.isoformat() if peer.last_handshake else None,
                'bytes_sent': peer.bytes_sent,
                'bytes_received': peer.bytes_received,
                'sent_mb': peer.get_sent_mb(),
                'received_mb': peer.get_received_mb(),
            })
        
        return JsonResponse({'peers': stats})
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def get_qr_code(request):
    """Генерація QR коду для конфігурації"""
    
    peer_id = request.GET.get('peer_id')
    if not peer_id:
        return JsonResponse({'error': 'Не вказано ID peer\'а'}, status=400)
    
    try:
        peer = get_object_or_404(WireGuardPeer, id=peer_id)
        
        # Перевіряємо права доступу
        if not request.user.is_superuser and peer.user != request.user:
            return JsonResponse({'error': 'Немає доступу'}, status=403)
        
        # Генеруємо конфігурацію
        config_content = generate_wireguard_config(peer)
        
        # Створюємо QR код
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(config_content)
        qr.make(fit=True)
        
        # Конвертуємо в base64
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return JsonResponse({
            'qr_code': f"data:image/png;base64,{qr_base64}",
            'config_name': peer.name
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
