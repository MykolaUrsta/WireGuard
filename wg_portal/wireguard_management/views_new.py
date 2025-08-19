"""
NOTE: This module contains an alternative implementation of locations/devices UI.
It is currently NOT used — the project URLs are wired to wireguard_management.views
and the separate `locations` app. We keep this file for reference, but it's not
loaded by Django routing. If you plan to switch to this UI, wire it in urls.py
and ensure corresponding templates exist.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count
from locations.models import Location, Device, DeviceGroup, ACLRule, UserLocationAccess
from .forms import LocationForm, DeviceForm, DeviceGroupForm, ACLRuleForm, UserLocationAccessForm
import subprocess
import qrcode
from io import BytesIO
import base64


@login_required
def locations_list(request):
    """Список всіх локацій"""
    locations = Location.objects.annotate(
        device_count=Count('devices'),
        user_count=Count('user_access')
    ).order_by('name')
    
    context = {
        'locations': locations,
        'page_title': 'Локації'
    }
    return render(request, 'wireguard_management/locations/list.html', context)


@login_required
def location_create(request):
    """Створення нової локації"""
    if request.method == 'POST':
        form = LocationForm(request.POST)
        if form.is_valid():
            location = form.save()
            # Генеруємо ключі для сервера
            generate_server_keys(location)
            messages.success(request, f'Локацію "{location.name}" успішно створено!')
            return redirect('wireguard_management:location_detail', pk=location.pk)
    else:
        form = LocationForm()
    
    context = {
        'form': form,
        'page_title': 'Створити локацію'
    }
    return render(request, 'wireguard_management/locations/create.html', context)


@login_required
def location_detail(request, pk):
    """Деталі локації"""
    location = get_object_or_404(Location, pk=pk)
    devices = location.devices.select_related('user', 'group').order_by('-created_at')
    acl_rules = location.acl_rules.select_related('source_group').order_by('priority')
    
    # Статистика
    stats = {
        'total_devices': devices.count(),
        'active_devices': devices.filter(status='active').count(),
        'online_devices': sum(1 for device in devices if device.is_online),
        'total_users': location.user_access.count(),
    }
    
    context = {
        'location': location,
        'devices': devices,
        'acl_rules': acl_rules,
        'stats': stats,
        'page_title': f'Локація: {location.name}'
    }
    return render(request, 'wireguard_management/locations/detail.html', context)


@login_required
def location_edit(request, pk):
    """Редагування локації"""
    location = get_object_or_404(Location, pk=pk)
    
    if request.method == 'POST':
        form = LocationForm(request.POST, instance=location)
        if form.is_valid():
            form.save()
            messages.success(request, f'Локацію "{location.name}" оновлено!')
            return redirect('wireguard_management:location_detail', pk=location.pk)
    else:
        form = LocationForm(instance=location)
    
    context = {
        'form': form,
        'location': location,
        'page_title': f'Редагувати: {location.name}'
    }
    return render(request, 'wireguard_management/locations/edit.html', context)


@login_required
def location_delete(request, pk):
    """Видалення локації"""
    location = get_object_or_404(Location, pk=pk)
    
    if request.method == 'POST':
        name = location.name
        location.delete()
        messages.success(request, f'Локацію "{name}" видалено!')
        return redirect('wireguard_management:locations')
    
    context = {
        'location': location,
        'page_title': f'Видалити: {location.name}'
    }
    return render(request, 'wireguard_management/locations/delete.html', context)


@login_required
def users_list(request):
    """Список користувачів з доступами"""
    users = User.objects.prefetch_related('location_access__location', 'devices').order_by('username')
    
    context = {
        'users': users,
        'page_title': 'Користувачі'
    }
    return render(request, 'wireguard_management/users/list.html', context)


@login_required
def user_detail(request, pk):
    """Деталі користувача"""
    user = get_object_or_404(User, pk=pk)
    devices = user.devices.select_related('location').order_by('-created_at')
    location_access = user.location_access.select_related('location').order_by('location__name')
    
    context = {
        'user_obj': user,  # Уникаємо конфлікту з контекстним user
        'devices': devices,
        'location_access': location_access,
        'page_title': f'Користувач: {user.username}'
    }
    return render(request, 'wireguard_management/users/detail.html', context)


@login_required
def grant_location_access(request, pk):
    """Надання доступу до локації"""
    user_obj = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        form = UserLocationAccessForm(request.POST)
        if form.is_valid():
            access = form.save(commit=False)
            access.user = user_obj
            access.granted_by = request.user
            access.save()
            messages.success(request, f'Доступ до локації "{access.location.name}" надано!')
            return redirect('wireguard_management:user_detail', pk=user_obj.pk)
    else:
        form = UserLocationAccessForm()
    
    context = {
        'form': form,
        'user_obj': user_obj,
        'page_title': f'Надати доступ: {user_obj.username}'
    }
    return render(request, 'wireguard_management/users/grant_access.html', context)


@login_required
def devices_list(request):
    """Список всіх пристроїв"""
    devices = Device.objects.select_related('user', 'location', 'group').order_by('-created_at')
    
    # Фільтрація
    location_filter = request.GET.get('location')
    status_filter = request.GET.get('status')
    
    if location_filter:
        devices = devices.filter(location_id=location_filter)
    if status_filter:
        devices = devices.filter(status=status_filter)
    
    locations = Location.objects.all()
    
    context = {
        'devices': devices,
        'locations': locations,
        'current_location': location_filter,
        'current_status': status_filter,
        'page_title': 'Пристрої'
    }
    return render(request, 'wireguard_management/devices/list.html', context)


@login_required
def device_create(request):
    """Створення нового пристрою"""
    if request.method == 'POST':
        form = DeviceForm(request.POST)
        if form.is_valid():
            device = form.save(commit=False)
            device.user = request.user
            
            # Генеруємо ключі
            generate_device_keys(device)
            
            # Призначаємо IP
            device.ip_address = device.location.next_available_ip
            if not device.ip_address:
                messages.error(request, 'Немає доступних IP адрес в цій локації!')
                return render(request, 'wireguard_management/devices/create.html', {'form': form})
            
            device.save()
            messages.success(request, f'Пристрій "{device.name}" створено!')
            return redirect('wireguard_management:device_detail', pk=device.pk)
    else:
        form = DeviceForm()
        # Фільтруємо локації доступні користувачу
        if not request.user.is_superuser:
            form.fields['location'].queryset = Location.objects.filter(
                user_access__user=request.user
            )
    
    context = {
        'form': form,
        'page_title': 'Створити пристрій'
    }
    return render(request, 'wireguard_management/devices/create.html', context)


@login_required
def device_detail(request, pk):
    """Деталі пристрою"""
    device = get_object_or_404(Device, pk=pk)
    
    # Перевіряємо права доступу
    if not request.user.is_superuser and device.user != request.user:
        messages.error(request, 'Ви не маєте доступу до цього пристрою!')
        return redirect('wireguard_management:devices')
    
    context = {
        'device': device,
        'page_title': f'Пристрій: {device.name}'
    }
    return render(request, 'wireguard_management/devices/detail.html', context)


@login_required
def device_config(request, pk):
    """Конфігурація WireGuard для пристрою"""
    device = get_object_or_404(Device, pk=pk)
    
    # Перевіряємо права доступу
    if not request.user.is_superuser and device.user != request.user:
        messages.error(request, 'Ви не маєте доступу до цього пристрою!')
        return redirect('wireguard_management:devices')
    
    # Генеруємо конфігурацію
    config = generate_device_config(device)
    
    # Генеруємо QR код
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(config)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    qr_code = base64.b64encode(buffer.getvalue()).decode()
    
    context = {
        'device': device,
        'config': config,
        'qr_code': qr_code,
        'page_title': f'Конфігурація: {device.name}'
    }
    return render(request, 'wireguard_management/devices/config.html', context)


@login_required
def device_delete(request, pk):
    """Видалення пристрою"""
    device = get_object_or_404(Device, pk=pk)
    
    # Перевіряємо права доступу
    if not request.user.is_superuser and device.user != request.user:
        messages.error(request, 'Ви не маєте доступу до цього пристрою!')
        return redirect('wireguard_management:devices')
    
    if request.method == 'POST':
        name = device.name
        device.delete()
        messages.success(request, f'Пристрій "{name}" видалено!')
        return redirect('wireguard_management:devices')
    
    context = {
        'device': device,
        'page_title': f'Видалити: {device.name}'
    }
    return render(request, 'wireguard_management/devices/delete.html', context)


@login_required
def acl_rules(request, location_pk):
    """ACL правила для локації"""
    location = get_object_or_404(Location, pk=location_pk)
    rules = location.acl_rules.select_related('source_group').order_by('priority')
    
    context = {
        'location': location,
        'rules': rules,
        'page_title': f'ACL правила: {location.name}'
    }
    return render(request, 'wireguard_management/acl/list.html', context)


@login_required
def acl_rule_create(request, location_pk):
    """Створення ACL правила"""
    location = get_object_or_404(Location, pk=location_pk)
    
    if request.method == 'POST':
        form = ACLRuleForm(request.POST)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.location = location
            rule.save()
            messages.success(request, f'ACL правило "{rule.name}" створено!')
            return redirect('wireguard_management:acl_rules', location_pk=location.pk)
    else:
        form = ACLRuleForm()
    
    context = {
        'form': form,
        'location': location,
        'page_title': f'Створити ACL правило: {location.name}'
    }
    return render(request, 'wireguard_management/acl/create.html', context)


@login_required
def device_groups(request):
    """Групи пристроїв"""
    groups = DeviceGroup.objects.annotate(device_count=Count('devices')).order_by('name')
    
    context = {
        'groups': groups,
        'page_title': 'Групи пристроїв'
    }
    return render(request, 'wireguard_management/groups/list.html', context)


# Допоміжні функції
def generate_server_keys(location):
    """Генерація ключів для сервера"""
    try:
        # Генеруємо приватний ключ
        private_key = subprocess.check_output(['wg', 'genkey'], text=True).strip()
        
        # Генеруємо публічний ключ
        public_key = subprocess.check_output(
            ['wg', 'pubkey'], 
            input=private_key, 
            text=True
        ).strip()
        
        location.private_key = private_key
        location.public_key = public_key
        location.save()
        
    except subprocess.CalledProcessError:
        pass  # Ігноруємо помилки генерації


def generate_device_keys(device):
    """Генерація ключів для пристрою"""
    try:
        # Генеруємо приватний ключ
        private_key = subprocess.check_output(['wg', 'genkey'], text=True).strip()
        
        # Генеруємо публічний ключ
        public_key = subprocess.check_output(
            ['wg', 'pubkey'], 
            input=private_key, 
            text=True
        ).strip()
        
        device.private_key = private_key
        device.public_key = public_key
        
    except subprocess.CalledProcessError:
        # Якщо wg недоступний, генеруємо фейкові ключі
        import secrets
        import base64
        
        private_bytes = secrets.token_bytes(32)
        device.private_key = base64.b64encode(private_bytes).decode()
        
        public_bytes = secrets.token_bytes(32)
        device.public_key = base64.b64encode(public_bytes).decode()


def generate_device_config(device):
    """Генерація конфігурації WireGuard для пристрою"""
    location = device.location
    
    config = f"""[Interface]
PrivateKey = {device.private_key}
Address = {device.ip_address}/32
DNS = {location.dns_servers}

[Peer]
PublicKey = {location.public_key}
Endpoint = {location.server_ip}:{location.server_port}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
"""
    return config
