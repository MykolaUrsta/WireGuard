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
    """Перенаправляє на детальну сторінку дефолтної локації"""
    # Перевіряємо чи є локації
    location_count = Location.objects.count()
    
    if location_count == 0:
        # Створюємо дефолтну локацію
        location = Location.objects.create(
            name="Головний офіс",
            description="Основна локація для WireGuard VPN",
            server_ip="10.0.0.1",
            server_port=51820,
            subnet="10.0.0.0/24",
            interface_name="wg0",
            is_active=True
        )
        return redirect('locations:detail', pk=location.pk)
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
        form = LocationForm(request.POST)
        if form.is_valid():
            location = form.save()
            messages.success(request, f'Локація "{location.name}" успішно створена!')
            return redirect('locations:detail', pk=location.pk)
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
    online_devices = location.devices.filter(status='active').count()
    
    context = {
        'location': location,
        'networks': networks,
        'total_devices': total_devices,
        'online_devices': online_devices,
    }
    
    return render(request, 'locations/detail.html', context)


@login_required
@user_passes_test(is_staff)
def location_edit(request, pk):
    """Редагування локації"""
    location = get_object_or_404(Location, pk=pk)
    
    if request.method == 'POST':
        form = LocationForm(request.POST, instance=location)
        if form.is_valid():
            form.save()
            messages.success(request, f'Локація "{location.name}" оновлена!')
            return redirect('locations:detail', pk=location.pk)
    else:
        form = LocationForm(instance=location)
    
    context = {
        'form': form,
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
def my_devices(request):
    """Пристрої поточного користувача"""
    devices = Device.objects.filter(user=request.user).select_related('network__location').order_by('-created_at')
    
    context = {
        'devices': devices,
    }
    
    return render(request, 'locations/my_devices.html', context)


@login_required
def device_create(request):
    """Створення нового пристрою"""
    if request.method == 'POST':
        form = DeviceForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                device = form.save()
                messages.success(request, f'Пристрій "{device.name}" створено!')
                return redirect('locations:device_detail', pk=device.pk)
            except Exception as e:
                messages.error(request, f'Помилка створення пристрою: {str(e)}')
    else:
        form = DeviceForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Додати пристрій'
    }
    
    return render(request, 'locations/device_create.html', context)


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
        'status_display': 'connected' if device.status == 'active' else 'disconnected'
    })
