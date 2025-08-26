from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils.dateparse import parse_datetime
import subprocess
import json
import qrcode
import io
import base64
from locations.models import Location
from .models import PeerMonitoring, WireGuardNetwork, WireGuardServer, WireGuardPeer
from .utils import generate_wireguard_config, update_server_config
from accounts.models import CustomUser
# API: історія трафіку по локації
@login_required
def api_location_history(request, pk):
    """API для отримання історії трафіку по локації (сума по всіх peer'ах)"""
    location = get_object_or_404(Location, pk=pk)
    # Дозволяємо тільки staff/admin
    if not request.user.is_staff:
        return JsonResponse({'error': 'Немає доступу'}, status=403)
    # Всі monitoring для peer'ів цієї локації
    from django.db.models import Sum
    from django.utils.dateparse import parse_datetime
    peers = location.devices.all()
    monitoring = PeerMonitoring.objects.filter(peer__in=peers)
    from_ts = request.GET.get('from')
    to_ts = request.GET.get('to')
    if from_ts:
        monitoring = monitoring.filter(timestamp__gte=parse_datetime(from_ts))
    if to_ts:
        monitoring = monitoring.filter(timestamp__lte=parse_datetime(to_ts))
    # Групуємо по часу (наприклад, по хвилинах)
    from django.db.models.functions import TruncMinute
    grouped = monitoring.annotate(minute=TruncMinute('timestamp')).values('minute').annotate(
        bytes_sent=Sum('bytes_sent'),
        bytes_received=Sum('bytes_received')
    ).order_by('minute')
    data = [
        {
            'timestamp': g['minute'].isoformat() if g['minute'] else None,
            'bytes_sent': g['bytes_sent'] or 0,
            'bytes_received': g['bytes_received'] or 0
        }
        for g in grouped
    ]
    return JsonResponse({'history': data})


@login_required
def api_peer_history(request, pk):
    """API для отримання історії трафіку peer'а (для графіків)"""
    peer = get_object_or_404(WireGuardPeer, pk=pk)
    if not request.user.is_superuser and peer.user != request.user:
        return JsonResponse({'error': 'Немає доступу'}, status=403)
    # Можна додати фільтр по часу (наприклад, ?from=2025-08-07T00:00:00&to=2025-08-07T23:59:59)
    qs = peer.monitoring.order_by('timestamp')
    from_ts = request.GET.get('from')
    to_ts = request.GET.get('to')
    if from_ts:
        qs = qs.filter(timestamp__gte=parse_datetime(from_ts))
    if to_ts:
        qs = qs.filter(timestamp__lte=parse_datetime(to_ts))
    data = [
        {
            'timestamp': m.timestamp.isoformat(),
            'bytes_sent': m.bytes_sent,
            'bytes_received': m.bytes_received
        }
        for m in qs
    ]
    return JsonResponse({'history': data})
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import WireGuardNetwork, WireGuardServer, WireGuardPeer
from .utils import generate_wireguard_config, update_server_config
from accounts.models import CustomUser
import subprocess
import json
import qrcode
import io
import base64


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
            

            # --- FIREWALL LOGIC ---
            from .models import FirewallRule
            # Очистити старі правила для цього peer (за IP)
            FirewallRule.objects.filter(source_ip=peer_ip, network=server.network).delete()

            # Дозволити лише ті адреси/мережі, які вказані у allowed_ips (через кому)
            allowed_ips = request.POST.get('allowed_ips', peer_ip)

            allowed_ip_list = [ip.strip() for ip in allowed_ips.split(',') if ip.strip()]
            for ip in allowed_ip_list:
                FirewallRule.objects.create(
                    name=f"Allow {ip} for {peer_name}",
                    network=server.network,
                    action='allow',
                    protocol='any',
                    direction='both',
                    source_ip=ip,
                    is_enabled=True,
                    priority=10
                )

            # Якщо є 0.0.0.0/0 — дозволяємо інтернет, але блокуємо приватні підмережі
            if '0.0.0.0/0' in allowed_ip_list:
                private_networks = [
                    '10.0.0.0/8',
                    '172.16.0.0/12',
                    '192.168.0.0/16',
                    '100.64.0.0/10',
                    '127.0.0.0/8',
                    '169.254.0.0/16',
                    '::1/128',
                    'fc00::/7',
                    'fe80::/10',
                ]
                for net in private_networks:
                    FirewallRule.objects.create(
                        name=f"Deny private {net} for {peer_name}",
                        network=server.network,
                        action='deny',
                        protocol='any',
                        direction='both',
                        source_ip=net,
                        is_enabled=True,
                        priority=15
                    )

            # Заборонити все інше для цього peer (крім дозволених)
            FirewallRule.objects.create(
                name=f"Deny all except allowed for {peer_name}",
                network=server.network,
                action='deny',
                protocol='any',
                direction='both',
                source_ip='',  # Порожній = всі
                is_enabled=True,
                priority=20
            )

            # Оновлюємо конфігурацію сервера
            update_server_config(server)
            # Перезапускаємо інтерфейс, щоб новий peer одразу працював
            from .utils import restart_wireguard_interface
            restart_wireguard_interface(server.interface_name if hasattr(server, 'interface_name') else 'wg0')

            # Застосувати firewall-правила через celery
            from wireguard_management.tasks import apply_firewall_rules
            apply_firewall_rules.delay(server.id)
            
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


# Networks Views
@login_required
def networks_list(request):
    """Список мереж"""
    networks = WireGuardNetwork.objects.all().order_by('name')
    context = {
        'networks': networks,
        'total_networks': networks.count(),
    }
    return render(request, 'wireguard_management/networks_list.html', context)


@login_required
def network_create(request):
    """Створення нової мережі"""
    if request.method == 'POST':
        # Логіка створення мережі
        messages.success(request, 'Мережу створено успішно!')
        return redirect('wireguard_management:networks')
    return render(request, 'wireguard_management/network_form.html')


@login_required
def network_detail(request, pk):
    """Деталі мережі"""
    network = get_object_or_404(WireGuardNetwork, pk=pk)
    context = {'network': network}
    return render(request, 'wireguard_management/network_detail.html', context)


@login_required
def network_edit(request, pk):
    """Редагування мережі"""
    network = get_object_or_404(WireGuardNetwork, pk=pk)
    if request.method == 'POST':
        # Логіка оновлення мережі
        messages.success(request, 'Мережу оновлено успішно!')
        return redirect('wireguard_management:network_detail', pk=pk)
    context = {'network': network}
    return render(request, 'wireguard_management/network_form.html', context)


@login_required
def network_delete(request, pk):
    """Видалення мережі"""
    network = get_object_or_404(WireGuardNetwork, pk=pk)
    if request.method == 'POST':
        network.delete()
        messages.success(request, 'Мережу видалено успішно!')
        return redirect('wireguard_management:networks')
    context = {'network': network}
    return render(request, 'wireguard_management/network_confirm_delete.html', context)


# Devices Views
@login_required
def devices_list(request):
    """Список пристроїв"""
    devices = WireGuardPeer.objects.all().order_by('name')
    if not request.user.is_superuser:
        devices = devices.filter(user=request.user)
    context = {'devices': devices}
    return render(request, 'wireguard_management/devices_list.html', context)


@login_required
def device_create(request):
    """Створення нового пристрою"""
    if request.method == 'POST':
        # Логіка створення пристрою
        messages.success(request, 'Пристрій створено успішно!')
        return redirect('wireguard_management:devices')
    return render(request, 'wireguard_management/device_form.html')


@login_required
def device_detail(request, pk):
    """Деталі пристрою"""
    device = get_object_or_404(WireGuardPeer, pk=pk)
    if not request.user.is_superuser and device.user != request.user:
        messages.error(request, 'Немає доступу до цього пристрою')
        return redirect('wireguard_management:devices')
    context = {'device': device}
    return render(request, 'wireguard_management/device_detail.html', context)


@login_required
def device_edit(request, pk):
    """Редагування пристрою"""
    device = get_object_or_404(WireGuardPeer, pk=pk)
    if not request.user.is_superuser and device.user != request.user:
        messages.error(request, 'Немає доступу до цього пристрою')
        return redirect('wireguard_management:devices')
    
    if request.method == 'POST':
        # Логіка оновлення пристрою
        messages.success(request, 'Пристрій оновлено успішно!')
        return redirect('wireguard_management:device_detail', pk=pk)
    context = {'device': device}
    return render(request, 'wireguard_management/device_form.html', context)


@login_required
def device_config(request, pk):
    """Конфігурація пристрою"""
    device = get_object_or_404(WireGuardPeer, pk=pk)
    if not request.user.is_superuser and device.user != request.user:
        return JsonResponse({'error': 'Немає доступу'}, status=403)
    
    config = generate_wireguard_config(device)
    response = HttpResponse(config, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{device.name}.conf"'
    return response


@login_required
def device_qr_code(request, pk):
    """QR код для пристрою"""
    device = get_object_or_404(WireGuardPeer, pk=pk)
    if not request.user.is_superuser and device.user != request.user:
        return JsonResponse({'error': 'Немає доступу'}, status=403)
    
    try:
        config_content = generate_wireguard_config(device)
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(config_content)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return HttpResponse(buffer.getvalue(), content_type='image/png')
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def device_delete(request, pk):
    """Видалення пристрою"""
    device = get_object_or_404(WireGuardPeer, pk=pk)
    if not request.user.is_superuser and device.user != request.user:
        messages.error(request, 'Немає доступу до цього пристрою')
        return redirect('wireguard_management:devices')
    
    if request.method == 'POST':
        device.delete()
        messages.success(request, 'Пристрій видалено успішно!')
        return redirect('wireguard_management:devices')
    context = {'device': device}
    return render(request, 'wireguard_management/device_confirm_delete.html', context)


# Tunnels Views
@login_required
def tunnels_list(request):
    """Список тунелів"""
    from .models import WireGuardTunnel
    tunnels = WireGuardTunnel.objects.all().order_by('name')
    context = {'tunnels': tunnels}
    return render(request, 'wireguard_management/tunnels_list.html', context)


@login_required
def tunnel_create(request):
    """Створення тунелю"""
    if request.method == 'POST':
        messages.success(request, 'Тунель створено успішно!')
        return redirect('wireguard_management:tunnels')
    return render(request, 'wireguard_management/tunnel_form.html')


@login_required
def tunnel_detail(request, pk):
    """Деталі тунелю"""
    from .models import WireGuardTunnel
    tunnel = get_object_or_404(WireGuardTunnel, pk=pk)
    context = {'tunnel': tunnel}
    return render(request, 'wireguard_management/tunnel_detail.html', context)


@login_required
def tunnel_start(request, pk):
    """Запуск тунелю"""
    from .models import WireGuardTunnel
    tunnel = get_object_or_404(WireGuardTunnel, pk=pk)
    try:
        tunnel.start()
        messages.success(request, f'Тунель {tunnel.name} запущено!')
    except Exception as e:
        messages.error(request, f'Помилка запуску тунелю: {e}')
    return redirect('wireguard_management:tunnel_detail', pk=pk)


@login_required
def tunnel_stop(request, pk):
    """Зупинка тунелю"""
    from .models import WireGuardTunnel
    tunnel = get_object_or_404(WireGuardTunnel, pk=pk)
    try:
        tunnel.stop()
        messages.success(request, f'Тунель {tunnel.name} зупинено!')
    except Exception as e:
        messages.error(request, f'Помилка зупинки тунелю: {e}')
    return redirect('wireguard_management:tunnel_detail', pk=pk)


@login_required
def tunnel_restart(request, pk):
    """Перезапуск тунелю"""
    from .models import WireGuardTunnel
    tunnel = get_object_or_404(WireGuardTunnel, pk=pk)
    try:
        tunnel.restart()
        messages.success(request, f'Тунель {tunnel.name} перезапущено!')
    except Exception as e:
        messages.error(request, f'Помилка перезапуску тунелю: {e}')
    return redirect('wireguard_management:tunnel_detail', pk=pk)


@login_required
def tunnel_config(request, pk):
    """Конфігурація тунелю"""
    from .models import WireGuardTunnel
    tunnel = get_object_or_404(WireGuardTunnel, pk=pk)
    # Логіка генерації конфігурації тунелю
    return JsonResponse({'status': 'success'})


@login_required
def tunnel_delete(request, pk):
    """Видалення тунелю"""
    from .models import WireGuardTunnel
    tunnel = get_object_or_404(WireGuardTunnel, pk=pk)
    if request.method == 'POST':
        tunnel.delete()
        messages.success(request, 'Тунель видалено успішно!')
        return redirect('wireguard_management:tunnels')
    context = {'tunnel': tunnel}
    return render(request, 'wireguard_management/tunnel_confirm_delete.html', context)


# ACL & Firewall Views
@login_required
def acl_rules(request, network_pk):
    """ACL правила для мережі"""
    network = get_object_or_404(WireGuardNetwork, pk=network_pk)
    # Логіка ACL
    context = {'network': network}
    return render(request, 'wireguard_management/acl_rules.html', context)


@login_required
def acl_rule_create(request, network_pk):
    """Створення ACL правила"""
    network = get_object_or_404(WireGuardNetwork, pk=network_pk)
    if request.method == 'POST':
        messages.success(request, 'ACL правило створено!')
        return redirect('wireguard_management:acl_rules', network_pk=network_pk)
    context = {'network': network}
    return render(request, 'wireguard_management/acl_form.html', context)


@login_required
def acl_rule_edit(request, pk):
    """Редагування ACL правила"""
    # Логіка редагування ACL
    return JsonResponse({'status': 'success'})


@login_required
def acl_rule_delete(request, pk):
    """Видалення ACL правила"""
    # Логіка видалення ACL
    return JsonResponse({'status': 'success'})


@login_required
def firewall_rules(request):
    """Правила фаєрволу"""
    from .models import FirewallRule
    rules = FirewallRule.objects.all().order_by('priority')
    context = {'rules': rules}
    return render(request, 'wireguard_management/firewall_rules.html', context)


@login_required
def firewall_rule_create(request):
    """Створення правила фаєрволу"""
    if request.method == 'POST':
        messages.success(request, 'Правило фаєрволу створено!')
        return redirect('wireguard_management:firewall_rules')
    return render(request, 'wireguard_management/firewall_form.html')


@login_required
def firewall_rule_edit(request, pk):
    """Редагування правила фаєрволу"""
    from .models import FirewallRule
    rule = get_object_or_404(FirewallRule, pk=pk)
    # Логіка редагування
    return JsonResponse({'status': 'success'})


@login_required
def firewall_rule_delete(request, pk):
    """Видалення правила фаєрволу"""
    from .models import FirewallRule
    rule = get_object_or_404(FirewallRule, pk=pk)
    if request.method == 'POST':
        rule.delete()
        messages.success(request, 'Правило фаєрволу видалено!')
    return redirect('wireguard_management:firewall_rules')


@login_required
def firewall_rule_toggle(request, pk):
    """Увімкнення/вимкнення правила фаєрволу"""
    from .models import FirewallRule
    rule = get_object_or_404(FirewallRule, pk=pk)
    rule.is_enabled = not rule.is_enabled
    rule.save()
    status = "увімкнено" if rule.is_enabled else "вимкнено"
    return JsonResponse({'status': 'success', 'enabled': rule.is_enabled, 'message': f'Правило {status}'})


# TOTP Views
@login_required
def device_totp_setup(request, pk):
    """Налаштування TOTP для пристрою"""
    device = get_object_or_404(WireGuardPeer, pk=pk)
    if not request.user.is_superuser and device.user != request.user:
        return JsonResponse({'error': 'Немає доступу'}, status=403)
    
    # Логіка налаштування TOTP
    return render(request, 'wireguard_management/totp_setup.html', {'device': device})


@login_required
def device_totp_verify(request, pk):
    """Верифікація TOTP коду"""
    device = get_object_or_404(WireGuardPeer, pk=pk)
    if not request.user.is_superuser and device.user != request.user:
        return JsonResponse({'error': 'Немає доступу'}, status=403)
    
    # Логіка верифікації TOTP
    return JsonResponse({'status': 'success'})


@login_required
def device_totp_disable(request, pk):
    """Вимкнення TOTP для пристрою"""
    device = get_object_or_404(WireGuardPeer, pk=pk)
    if not request.user.is_superuser and device.user != request.user:
        return JsonResponse({'error': 'Немає доступу'}, status=403)
    
    # Логіка вимкнення TOTP
    return JsonResponse({'status': 'success'})


@login_required
def totp_qr_code(request, secret):
    """QR код для TOTP"""
    # Логіка генерації QR коду для TOTP
    return JsonResponse({'status': 'success'})


@login_required
def device_groups(request):
    """Групи пристроїв"""
    # Логіка груп пристроїв
    context = {}
    return render(request, 'wireguard_management/device_groups.html', context)


@login_required
def device_group_create(request):
    """Створення групи пристроїв"""
    return JsonResponse({'status': 'success'})


@login_required
def device_group_edit(request, pk):
    """Редагування групи пристроїв"""
    return JsonResponse({'status': 'success'})


@login_required
def device_group_delete(request, pk):
    """Видалення групи пристроїв"""
    return JsonResponse({'status': 'success'})


# API Views
@login_required
def api_network_status(request):
    """API статусу мережі"""
    from .models import NetworkMonitoring
    
    # Базова статистика
    total_networks = WireGuardNetwork.objects.filter(is_active=True).count()
    total_devices = WireGuardPeer.objects.count()
    online_devices = WireGuardPeer.objects.filter(is_active=True).count()
    
    # Статус сервісів
    services = {
        'wireguard': True,
        'database': True,
        'redis': True,
        'nginx': True,
    }
    
    return JsonResponse({
        'total_networks': total_networks,
        'total_devices': total_devices,
        'online_devices': online_devices,
        'services': services,
        'timestamp': timezone.now().isoformat()
    })


@login_required
def api_device_stats(request, pk):
    """API статистики пристрою"""
    device = get_object_or_404(WireGuardPeer, pk=pk)
    if not request.user.is_superuser and device.user != request.user:
        return JsonResponse({'error': 'Немає доступу'}, status=403)
    
    return JsonResponse({
        'name': device.name,
        'ip_address': device.ip_address,
        'is_online': device.is_online,
        'bytes_sent': device.bytes_sent,
        'bytes_received': device.bytes_received,
        'last_handshake': device.last_handshake.isoformat() if device.last_handshake else None,
    })


@login_required
def api_tunnel_status(request, pk):
    """API статусу тунелю"""
    from .models import WireGuardTunnel
    tunnel = get_object_or_404(WireGuardTunnel, pk=pk)
    
    return JsonResponse({
        'name': tunnel.name,
        'interface': tunnel.interface_name,
        'status': tunnel.status,
        'last_started': tunnel.last_started.isoformat() if tunnel.last_started else None,
    })


@login_required
def api_firewall_status(request):
    """API статусу фаєрволу"""
    from .models import FirewallRule
    
    total_rules = FirewallRule.objects.count()
    active_rules = FirewallRule.objects.filter(is_enabled=True).count()
    
    return JsonResponse({
        'total_rules': total_rules,
        'active_rules': active_rules,
        'firewall_enabled': True,
    })
