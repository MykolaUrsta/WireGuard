from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import user_passes_test
from .models import Location, Network, AccessControlList, Device
from .forms import LocationForm, NetworkForm, AccessControlListForm, DeviceForm, QuickNetworkForm
import json


def is_staff(user):
    return user.is_staff


@login_required
def locations_redirect(request):
    """Перенаправляє на детальну сторінку дефолтної локації або показує кнопку створення"""
    # Перевіряємо чи є локації
    location_count = Location.objects.count()
    
    if location_count == 0:
        # Якщо локацій немає - показуємо сторінку зі створенням
        return render(request, 'locations/empty_state.html')
    else:
        # Перенаправляємо на першу активну локацію або просто першу
        location = Location.objects.filter(is_active=True).first() or Location.objects.first()
        return redirect('locations:detail', pk=location.pk)


@login_required  
def default_location_detail(request):
    """Показує деталі дефолтної локації"""
    location = Location.objects.filter(is_active=True).first() or Location.objects.first()
    if not location:
        return redirect('locations:list')
    return redirect('locations:detail', pk=location.pk)


@login_required
def locations_list(request):
    """Список всіх локацій"""
    locations = Location.objects.all().order_by('name')
    
    # Додаємо статистику для кожної локації
    for location in locations:
        location.networks_count = location.networks.count()
        location.devices_count = location.devices.count()
        location.active_users_count = location.devices.filter(status='active').count()
        location.total_devices_count = location.devices.count()
        location.connected_users_count = location.devices.filter(status='active').count()
        location.is_active = location.networks.filter(is_active=True).exists()
        location.traffic_in = sum(d.bytes_received or 0 for d in location.devices.all())
        location.traffic_out = sum(d.bytes_sent or 0 for d in location.devices.all())
        
        # Отримуємо перші налаштування мережі
        first_network = location.networks.first()
        if first_network:
            location.network_subnet = first_network.subnet
            location.endpoint = first_network.endpoint
        else:
            location.network_subnet = None
            location.endpoint = None
    
    paginator = Paginator(locations, 12)  # 12 карток на сторінку
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'locations': page_obj,
        'total_locations': locations.count(),
        'total_networks': Network.objects.count(),
        'total_devices': Device.objects.count(),
        'online_devices': Device.objects.filter(status='active').count(),
    }
    
    return render(request, 'locations/list.html', context)


@login_required
@user_passes_test(is_staff)
def location_create(request):
    """Створення нової локації"""
    if request.method == 'POST':
        setup_type = request.POST.get('setup_type', 'quick')
        
        # Отримуємо дані з форми
        name = request.POST.get('name')
        server_ip = request.POST.get('server_ip')
        server_port = request.POST.get('server_port', 51820)
        subnet = request.POST.get('subnet', '10.0.0.0/24')
        interface_name = request.POST.get('interface_name', 'wg0')
        description = request.POST.get('description', '')
        dns_servers = request.POST.get('dns_servers', '1.1.1.1,8.8.8.8')
        allowed_ips = request.POST.get('allowed_ips', '0.0.0.0/0')
        public_key = request.POST.get('public_key', '')
        private_key = request.POST.get('private_key', '')
        is_active = request.POST.get('is_active') == 'on'
        
        try:
            # Генеруємо ключі якщо не вказані
            if not public_key or not private_key:
                import subprocess
                # Генеруємо приватний ключ
                private_key_result = subprocess.run(['wg', 'genkey'], capture_output=True, text=True)
                if private_key_result.returncode == 0:
                    private_key = private_key_result.stdout.strip()
                    # Генеруємо публічний ключ
                    public_key_result = subprocess.run(['wg', 'pubkey'], input=private_key, capture_output=True, text=True)
                    if public_key_result.returncode == 0:
                        public_key = public_key_result.stdout.strip()
            
            # Створюємо локацію
            location = Location.objects.create(
                name=name,
                description=description,
                server_ip=server_ip,
                server_port=int(server_port),
                subnet=subnet,
                interface_name=interface_name,
                public_key=public_key,
                private_key=private_key,
                dns_servers=dns_servers,
                allowed_ips=allowed_ips,
                is_active=is_active
            )
            
            # Оновлюємо WireGuard конфігурацію та перезапускаємо інтерфейс
            try:
                from .docker_manager import WireGuardDockerManager
                manager = WireGuardDockerManager()
                manager.generate_server_config(location)
                manager.restart_wireguard(location.interface_name)
                messages.info(request, 'WireGuard конфігурація згенерована та інтерфейс перезапущено!')
            except Exception as wg_error:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Помилка оновлення WireGuard після створення локації: {str(wg_error)}")
                messages.warning(request, f'Локація створена, але WireGuard конфігурація не оновилась: {str(wg_error)}')

            messages.success(request, f'Локація "{location.name}" успішно створена та налаштована!')
            return redirect('locations:detail', pk=location.pk)
            
        except Exception as e:
            messages.error(request, f'Помилка при створенні локації: {str(e)}')
            return redirect('locations:list')
    else:
        form = LocationForm()
    
    context = {
        'form': form,
        'title': 'Створити локацію'
    }
    
    return render(request, 'locations/create.html', context)


@login_required
def location_detail(request, pk):
    """Деталі локації"""
    location = get_object_or_404(Location, pk=pk)
    networks = location.networks.all().order_by('name')
    
    # Статистика
    total_devices = location.devices.count()
    devices = location.devices.all()
    online_devices = sum(1 for device in devices if device.is_online)
    
    # Статистика за останню годину
    from django.utils import timezone
    from datetime import timedelta
    one_hour_ago = timezone.now() - timedelta(hours=1)
    
    # Пристрої, що були активні за останню годину
    devices_last_hour = location.devices.filter(last_handshake__gte=one_hour_ago).count()
    
    # Унікальні користувачі, що були активні за останню годину
    users_last_hour = location.devices.filter(
        last_handshake__gte=one_hour_ago
    ).values('user').distinct().count()
    
    # Загальна статистика трафіку
    total_bytes_received = sum(device.bytes_received for device in devices)
    total_bytes_sent = sum(device.bytes_sent for device in devices)
    
    # Всі локації для навігації
    all_locations = Location.objects.all().order_by('name')
    
    context = {
        'location': location,
        'networks': networks,
        'total_devices': total_devices,
        'online_devices': online_devices,
        'devices_last_hour': devices_last_hour,
        'users_last_hour': users_last_hour,
        'total_bytes_received': total_bytes_received,
        'total_bytes_sent': total_bytes_sent,
        'all_locations': all_locations,
    }
    
    return render(request, 'locations/detail.html', context)


@login_required
@user_passes_test(is_staff)
def location_edit(request, pk):
    """Редагування локації"""
    location = get_object_or_404(Location, pk=pk)
    
    if request.method == 'POST':
        # Перевіряємо чи це запит на регенерацію ключів
        if request.POST.get('regenerate_keys'):
            try:
                import subprocess
                # Генеруємо новий приватний ключ
                private_key_result = subprocess.run(['wg', 'genkey'], capture_output=True, text=True)
                if private_key_result.returncode == 0:
                    private_key = private_key_result.stdout.strip()
                    # Генеруємо новий публічний ключ
                    public_key_result = subprocess.run(['wg', 'pubkey'], input=private_key, capture_output=True, text=True)
                    if public_key_result.returncode == 0:
                        public_key = public_key_result.stdout.strip()
                        
                        # Оновлюємо ключі в локації
                        location.private_key = private_key
                        location.public_key = public_key
                        location.save()
                        
                        # Оновлюємо також в мережах цієї локації
                        for network in location.networks.all():
                            network.server_public_key = public_key
                            network.save()
                        
                        # Оновлюємо WireGuard конфігурацію з новими ключами
                        try:
                            from .docker_manager import WireGuardDockerManager
                            manager = WireGuardDockerManager()
                            manager.generate_server_config(location)
                            manager.restart_wireguard(location.interface_name)
                        except Exception as wg_error:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.error(f"Помилка оновлення WireGuard після регенерації ключів: {str(wg_error)}")
                        
                        return JsonResponse({
                            'success': True,
                            'public_key': public_key,
                            'private_key': private_key,
                            'message': 'Ключі регенеровано та WireGuard конфігурація оновлена!'
                        })
                return JsonResponse({'success': False, 'error': 'Помилка генерації ключів'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
        
        # Звичайне оновлення локації
        try:
            location.name = request.POST.get('name')
            location.description = request.POST.get('description', '')
            location.server_ip = request.POST.get('server_ip')
            location.server_port = int(request.POST.get('server_port'))
            location.subnet = request.POST.get('subnet')
            location.interface_name = request.POST.get('interface_name')
            location.dns_servers = request.POST.get('dns_servers')
            location.allowed_ips = request.POST.get('allowed_ips', '0.0.0.0/0')
            location.is_active = bool(request.POST.get('is_active'))
            location.save()
            
            # Оновлюємо також мережі цієї локації
            for network in location.networks.all():
                network.subnet = location.subnet
                network.interface = location.interface_name
                network.server_port = location.server_port
                network.listen_port = location.server_port
                network.dns_servers = location.dns_servers
                network.allowed_ips = location.allowed_ips
                network.save()
            
            # Явно оновлюємо WireGuard конфігурацію
            try:
                from .docker_manager import WireGuardDockerManager
                manager = WireGuardDockerManager()
                
                # Регенеруємо конфігурацію сервера
                if manager.generate_server_config(location):
                    # Перезапускаємо WireGuard інтерфейс
                    manager.restart_wireguard(location.interface_name)
                    messages.info(request, 'WireGuard конфігурація оновлена та застосована!')
                else:
                    messages.warning(request, 'Локація оновлена, але конфігурація WireGuard не змогла оновитись')
                    
            except Exception as wg_error:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Помилка оновлення WireGuard для локації {location.name}: {str(wg_error)}")
                messages.warning(request, f'Локація оновлена, але WireGuard конфігурація не оновилась: {str(wg_error)}')
            
            messages.success(request, f'Локація "{location.name}" оновлена!')
            return redirect('locations:detail', pk=location.pk)
        except Exception as e:
            messages.error(request, f'Помилка при оновленні: {str(e)}')
    
    context = {
        'location': location,
        'title': f'Редагувати {location.name}'
    }
    
    return render(request, 'locations/edit.html', context)


@login_required
@user_passes_test(is_staff)
def location_delete(request, pk):
    """Видалення локації"""
    location = get_object_or_404(Location, pk=pk)
    
    if request.method == 'POST':
        name = location.name
        location.delete()
        messages.success(request, f'Локація "{name}" видалена!')
        return redirect('locations:list')
    
    context = {
        'location': location,
        'networks_count': location.networks.count(),
    }
    
    return render(request, 'locations/delete.html', context)


@login_required
def networks_list(request):
    """Список всіх мереж"""
    networks = Network.objects.select_related('location').all().order_by('location__name', 'name')
    
    # Додаємо статистику
    for network in networks:
        network.devices_count = network.devices.count()
        network.online_devices = network.devices.filter(status='active').count()
    
    paginator = Paginator(networks, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'networks': page_obj,
    }
    
    return render(request, 'locations/networks_list.html', context)


@login_required
@user_passes_test(is_staff)
def network_create(request, location_pk=None):
    """Створення нової мережі"""
    location = None
    if location_pk:
        location = get_object_or_404(Location, pk=location_pk)
    
    if request.method == 'POST':
        form = NetworkForm(request.POST)
        if form.is_valid():
            network = form.save()
            messages.success(request, f'Мережа "{network.name}" створена!')
            return redirect('locations:network_detail', pk=network.pk)
    else:
        initial = {}
        if location:
            initial['location'] = location
        form = NetworkForm(initial=initial)
    
    context = {
        'form': form,
        'location': location,
        'title': 'Створити мережу'
    }
    
    return render(request, 'locations/network_create.html', context)


@login_required
def network_detail(request, pk):
    """Деталі мережі"""
    network = get_object_or_404(Network, pk=pk)
    devices = network.devices.select_related('user').all().order_by('user__username', 'name')
    
    # Доступні IP адреси
    available_ips = network.get_available_ips()[:10]  # Показуємо тільки перші 10
    
    context = {
        'network': network,
        'devices': devices,
        'available_ips': available_ips,
        'total_ips': len(network.get_available_ips()),
    }
    
    return render(request, 'locations/network_detail.html', context)


@login_required
@user_passes_test(is_staff)
def quick_setup(request):
    """Швидке налаштування - створення локації та мережі одразу"""
    if request.method == 'POST':
        form = QuickNetworkForm(request.POST)
        if form.is_valid():
            try:
                location, network = form.save()
                messages.success(
                    request, 
                    f'Локація "{location.name}" та мережа "{network.name}" створені!'
                )
                return redirect('locations:detail', pk=location.pk)
            except Exception as e:
                messages.error(request, f'Помилка створення: {str(e)}')
    else:
        form = QuickNetworkForm()
    
    context = {
        'form': form,
        'title': 'Швидке налаштування'
    }
    
    return render(request, 'locations/quick_setup.html', context)




@login_required
def device_create(request):
    """Створення нового пристрою"""
    import qrcode
    from io import BytesIO
    import base64
    import ipaddress
    
    if request.method == 'POST':
        try:
            device_name = request.POST.get('name', '').strip()
            location_id = request.POST.get('location_id')
            
            if not device_name or not location_id:
                return JsonResponse({'success': False, 'error': 'Назва пристрою та локація обов\'язкові'})
            

            # Якщо суперкористувач — дозволяємо створювати для іншого користувача
            if request.user.is_superuser and request.POST.get('user_id'):
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    user = User.objects.get(pk=request.POST.get('user_id'))
                except User.DoesNotExist:
                    return JsonResponse({'success': False, 'error': 'Користувача не знайдено'})
            else:
                user = request.user

            location = get_object_or_404(Location, pk=location_id)

            # Перевіряємо, чи вже існує пристрій з такою назвою у цього користувача
            if Device.objects.filter(user=user, name=device_name).exists():
                return JsonResponse({'success': False, 'error': 'У вас вже є пристрій з такою назвою. Виберіть іншу назву.'})
            
            # Завжди генеруємо нову пару ключів
            import subprocess
            import tempfile
            import os
            
            with tempfile.TemporaryDirectory() as temp_dir:
                private_key_path = os.path.join(temp_dir, 'private.key')
                public_key_path = os.path.join(temp_dir, 'public.key')
                
                # Генеруємо приватний ключ
                subprocess.run(['wg', 'genkey'], stdout=open(private_key_path, 'w'), check=True)
                
                # Генеруємо публічний ключ
                with open(private_key_path, 'r') as f:
                    subprocess.run(['wg', 'pubkey'], stdin=f, stdout=open(public_key_path, 'w'), check=True)
                
                with open(private_key_path, 'r') as f:
                    private_key = f.read().strip()
                with open(public_key_path, 'r') as f:
                    public_key = f.read().strip()
            
            # Отримуємо дефолтну мережу вибраної локації
            network = location.networks.first()
            if not network:
                # Якщо мережі немає, створюємо її автоматично з даних локації
                from .models import Network
                network = Network.objects.create(
                    name=f"{location.name} - Auto Network",
                    location=location,
                    subnet=location.subnet,
                    interface=location.interface_name,
                    server_port=location.server_port,
                    listen_port=location.server_port,
                    server_public_key=location.public_key,
                    server_ip=location.server_ip,
                    allowed_ips="0.0.0.0/0",
                    dns_servers=location.dns_servers,
                    is_active=True
                )
            
            # Генеруємо IP адресу для пристрою
            network_ip = ipaddress.IPv4Network(network.subnet)
            existing_ips = set(Device.objects.filter(network=network).values_list('ip_address', flat=True))
            
            # Знаходимо вільну IP адресу
            device_ip = None
            for ip in network_ip.hosts():
                if str(ip) not in existing_ips and str(ip) != network.server_ip:
                    device_ip = str(ip)
                    break
            
            if not device_ip:
                return JsonResponse({'success': False, 'error': 'Немає доступних IP адрес у мережі'})
            


            # Створюємо пристрій
            device = Device.objects.create(
                name=device_name,
                user=user,
                location=location,
                network=network,
                ip_address=device_ip,
                public_key=public_key,
                private_key=private_key,
                status='active'
            )

            # Створюємо peer тільки після успішного створення пристрою
            # Створюємо WireGuardPeer для пристрою, якщо такого ще немає
            from wireguard_management.models import WireGuardPeer, WireGuardServer, WireGuardNetwork
            if device and device.status == 'active':
                wg_network = None
                if device.network and device.network.subnet:
                    wg_network = WireGuardNetwork.objects.filter(network_cidr=device.network.subnet).first()
                if wg_network:
                    server = WireGuardServer.objects.filter(network=wg_network).first()
                    if server:
                        exists = WireGuardPeer.objects.filter(user=device.user, ip_address=device.ip_address).exists()
                        if not exists:
                            WireGuardPeer.objects.create(
                                user=device.user,
                                server=server,
                                name=device.name,
                                ip_address=device.ip_address,
                                public_key=device.public_key,
                                private_key=device.private_key,
                                allowed_ips='0.0.0.0/0',
                                is_active=True
                            )

            # Live-додавання peer до wg (без перезапуску)
            try:
                from .docker_manager import WireGuardDockerManager
                manager = WireGuardDockerManager()
                manager.add_peer_live(device)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Live add peer error: {str(e)}")
            
            # Генеруємо конфігурацію WireGuard
            config = f"""[Interface]
PrivateKey = {private_key}
Address = {device_ip}/32
DNS = {network.dns_servers or '8.8.8.8, 8.8.4.4'}

[Peer]
PublicKey = {network.server_public_key}
Endpoint = {location.server_ip}:{network.listen_port}
AllowedIPs = {network.allowed_ips or '0.0.0.0/0'}
PersistentKeepalive = 25
"""
            
            # Генеруємо QR код
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(config)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            qr_image = base64.b64encode(buffer.getvalue()).decode()
            
            return JsonResponse({
                'success': True,
                'device': {
                    'id': device.id,
                    'name': device.name,
                    'ip_address': device_ip,
                    'public_key': public_key,
                    'config': config
                },
                'qr_code': qr_image
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    # GET запит - показуємо форму
    locations = Location.objects.filter(is_active=True).order_by('name')
    context = {
        'locations': locations,
        'title': 'Додати пристрій',
    }
    # Якщо суперкористувач і є user_id у GET — передаємо у шаблон
    if request.user.is_superuser and request.GET.get('user_id'):
        context['user_id'] = request.GET.get('user_id')
    return render(request, 'locations/device_create.html', context)


@login_required
def device_config_download(request, device_id):
    """Завантаження конфігурації пристрою"""
    device = get_object_or_404(Device, pk=device_id)
    
    # Перевіряємо права доступу
    if not request.user.is_staff and device.user != request.user:
        return HttpResponse('Forbidden', status=403)
    
    # Генеруємо конфігурацію
    import ipaddress
    network_ip = ipaddress.IPv4Network(device.network.subnet)
    
    config = f"""[Interface]
PrivateKey = {device.private_key}
Address = {device.ip_address}/32
DNS = {device.network.dns_servers or '8.8.8.8, 8.8.4.4'}

[Peer]
PublicKey = {device.network.server_public_key}
Endpoint = {device.location.server_ip}:{device.network.listen_port}
AllowedIPs = {device.network.allowed_ips or '0.0.0.0/0'}
PersistentKeepalive = 25
"""
    
    response = HttpResponse(config, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{device.name}.conf"'
    return response


@login_required
def device_detail(request, pk):
    """Деталі пристрою"""
    device = get_object_or_404(Device, pk=pk)
    
    # Перевіряємо права доступу
    if not request.user.is_staff and device.user != request.user:
        messages.error(request, 'У вас немає прав для перегляду цього пристрою')
        return redirect('locations:my_devices')
    
    context = {
        'device': device,
        'config': device.get_config(),
    }
    
    return render(request, 'locations/device_detail.html', context)


@login_required
def device_config(request, pk):
    """Завантаження конфігурації пристрою"""
    device = get_object_or_404(Device, pk=pk)
    
    # Перевіряємо права доступу
    if not request.user.is_staff and device.user != request.user:
        messages.error(request, 'У вас немає прав для завантаження конфігурації')
        return redirect('locations:my_devices')
    
    config = device.get_config()
    filename = f"{device.name.replace(' ', '_')}.conf"
    
    response = HttpResponse(config, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


@login_required
@user_passes_test(is_staff)
def acl_list(request):
    """Список ACL правил"""
    acl_rules = AccessControlList.objects.all().order_by('name')
    
    context = {
        'acl_rules': acl_rules,
    }
    
    return render(request, 'locations/acl_list.html', context)


@login_required
@user_passes_test(is_staff)
def acl_create(request):
    """Створення ACL правила"""
    if request.method == 'POST':
        form = AccessControlListForm(request.POST)
        if form.is_valid():
            acl = form.save()
            messages.success(request, f'ACL правило "{acl.name}" створено!')
            return redirect('locations:acl_detail', pk=acl.pk)
    else:
        form = AccessControlListForm()
    
    context = {
        'form': form,
        'title': 'Створити ACL правило'
    }
    
    return render(request, 'locations/acl_create.html', context)


@login_required
@user_passes_test(is_staff)
def acl_detail(request, pk):
    """Деталі ACL правила"""
    acl = get_object_or_404(AccessControlList, pk=pk)
    
    context = {
        'acl': acl,
        'networks': acl.networks.all(),
        'devices': acl.devices.all(),
    }
    
    return render(request, 'locations/acl_detail.html', context)


# API endpoints для AJAX
@login_required
@require_http_methods(["GET"])
def api_network_info(request, pk):
    """API для отримання інформації про мережу"""
    network = get_object_or_404(Network, pk=pk)
    
    data = {
        'name': network.name,
        'subnet': network.subnet,
        'interface': network.interface,
        'devices_count': network.devices.count(),
        'online_devices': network.devices.filter(status='active').count(),
    }
    
    return JsonResponse(data)


@login_required
@require_http_methods(["POST"])
def api_toggle_device(request, pk):
    """API для вмикання/вимикання пристрою"""
    device = get_object_or_404(Device, pk=pk)
    
    # Перевіряємо права доступу
    if not request.user.is_staff and device.user != request.user:
        return JsonResponse({'error': 'Немає прав доступу'}, status=403)
    
    # Перемикаємо статус пристрою
    if device.status == 'active':
        device.status = 'inactive'
    else:
        device.status = 'active'
    device.save()
    
    return JsonResponse({
        'status': device.status,
        'is_active': device.status == 'active',
        'is_online': device.is_online,
        'status_display': 'connected' if device.is_online else 'disconnected'
    })


@login_required
@require_http_methods(["GET"])
def api_location_stats(request, pk):
    """API для отримання статистики локації"""
    location = get_object_or_404(Location, pk=pk)
    
    # Статистика
    devices = location.devices.all()
    online_devices = sum(1 for device in devices if device.is_online)
    
    # Статистика за останню годину
    from django.utils import timezone
    from datetime import timedelta
    one_hour_ago = timezone.now() - timedelta(hours=1)
    
    devices_last_hour = location.devices.filter(last_handshake__gte=one_hour_ago).count()
    users_last_hour = location.devices.filter(
        last_handshake__gte=one_hour_ago
    ).values('user').distinct().count()
    
    # Інформація про кожен пристрій
    from django.template.defaultfilters import filesizeformat
    devices_info = []
    for device in devices:
        # connection_time: скільки часу підключений (від connected_at, якщо онлайн)
        if device.is_online and device.connected_at:
            from django.utils import timezone
            duration = int((timezone.now() - device.connected_at).total_seconds())
            hours = duration // 3600
            minutes = (duration % 3600) // 60
            seconds = duration % 60
            if hours > 0:
                connection_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                connection_time = f"{minutes:02d}:{seconds:02d}"
        else:
            connection_time = None

        # Додаємо user-інформацію для фронта
        user_info = None
        if device.user:
            user_info = {
                'id': device.user.id,
                'username': device.user.username,
                'full_name': getattr(device.user, 'get_full_name', lambda: None)() or device.user.username
            }

        devices_info.append({
            'id': device.id,
            'is_online': device.is_online,
            'connected_at': device.connected_at.isoformat() if device.connected_at else None,
            'connection_time': connection_time,
            'bytes_received': device.bytes_received,
            'bytes_sent': device.bytes_sent,
            'bytes_received_human': filesizeformat(device.bytes_received),
            'bytes_sent_human': filesizeformat(device.bytes_sent),
            'user': user_info,
            'name': device.name,
            'public_key': device.public_key,
            'device_name': device.name,
        })
    
    data = {
        'online_devices': online_devices,
        'devices_last_hour': devices_last_hour,
        'users_last_hour': users_last_hour,
        'devices': devices_info,
    }
    
    return JsonResponse(data)


@login_required
@require_http_methods(["GET"])
def api_location_history(request, pk):
    """API для отримання історії трафіку по локації"""
    location = get_object_or_404(Location, pk=pk)
    
    # Дозволяємо всім авторизованим користувачам
    # В майбутньому можна додати перевірку прав
    
    # Повертаємо тестові дані для демонстрації
    # В реальному проекті тут буде запит до моніторингу
    from django.utils import timezone
    from datetime import timedelta
    import random
    
    # Генеруємо тестові дані за останню годину
    now = timezone.now()
    data = []
    
    for i in range(60):  # 60 точок за годину (кожна хвилина)
        timestamp = now - timedelta(minutes=60-i)
        # Симулюємо трафік
        bytes_sent = random.randint(100000, 1000000)  # 100KB - 1MB
        bytes_received = random.randint(50000, 500000)  # 50KB - 500KB
        
        data.append({
            'timestamp': timestamp.isoformat(),
            'bytes_sent': bytes_sent,
            'bytes_received': bytes_received
        })
    
    return JsonResponse({'history': data})


@login_required  
@require_http_methods(["GET"])
def api_peer_history(request, pk):
    """API для отримання історії трафіку пристрою"""
    device = get_object_or_404(Device, pk=pk)
    
    # Перевіряємо права доступу
    if not request.user.is_staff and device.user != request.user:
        return JsonResponse({'error': 'Немає прав доступу'}, status=403)
    
    # Повертаємо тестові дані для демонстрації
    from django.utils import timezone
    from datetime import timedelta
    import random
    
    # Генеруємо тестові дані за останню годину
    now = timezone.now()
    data = []
    
    for i in range(60):  # 60 точок за годину (кожна хвилина)
        timestamp = now - timedelta(minutes=60-i)
        # Симулюємо трафік для конкретного пристрою
        bytes_sent = random.randint(10000, 100000)  # 10KB - 100KB
        bytes_received = random.randint(5000, 50000)  # 5KB - 50KB
        
        data.append({
            'timestamp': timestamp.isoformat(),
            'bytes_sent': bytes_sent,
            'bytes_received': bytes_received
        })
    
    return JsonResponse({'history': data})


@login_required
@require_http_methods(["GET"])
def api_refresh_location_stats(request, pk):
    """API для швидкого оновлення статистик локації"""
    from django.core.management import call_command
    from io import StringIO
    
    location = get_object_or_404(Location, pk=pk)
    
    try:
        # Викликаємо швидку команду синхронізації
        out = StringIO()
        call_command('fast_sync_stats', interface=location.interface_name, stdout=out)
        
        # Підраховуємо оновлені пристрої
        updated_devices = location.devices.filter(status='active').count()
        
        return JsonResponse({
            'success': True,
            'updated_devices': updated_devices,
            'message': f'Статистики оновлені для інтерфейсу {location.interface_name}'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
