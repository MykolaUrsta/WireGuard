from django import template
from django.db.models import Count
from ..models import Location, Network, Device

register = template.Library()


@register.simple_tag
def get_total_locations():
    """Отримати загальну кількість локацій"""
    return Location.objects.count()


@register.simple_tag
def get_total_networks():
    """Отримати загальну кількість мереж"""
    return Network.objects.count()


@register.simple_tag
def get_online_devices():
    """Отримати кількість онлайн пристроїв"""
    return Device.objects.filter(status='active').count()


@register.simple_tag
def get_total_devices():
    """Отримати загальну кількість пристроїв"""
    return Device.objects.count()


@register.simple_tag
def get_network_stats():
    """Отримати статистику мереж"""
    return {
        'total_networks': Network.objects.count(),
        'total_devices': Device.objects.count(),
        'online_devices': Device.objects.filter(status='active').count(),
        'offline_devices': Device.objects.filter(status__in=['inactive', 'blocked']).count(),
    }


@register.inclusion_tag('components/network_status.html')
def network_status(network):
    """Відобразити статус мережі"""
    return {
        'network': network,
        'devices_count': network.devices.count(),
        'online_devices': network.devices.filter(status='active').count(),
    }


@register.inclusion_tag('components/device_status.html')
def device_status(device):
    """Відобразити статус пристрою"""
    return {'device': device}


@register.filter
def subnet_size(subnet):
    """Обчислити розмір підмережі"""
    try:
        import ipaddress
        network = ipaddress.ip_network(subnet, strict=False)
        return network.num_addresses - 2  # Віднімаємо network і broadcast
    except:
        return 0


@register.filter
def mask_to_cidr(mask):
    """Конвертувати маску в CIDR нотацію"""
    try:
        import ipaddress
        return str(ipaddress.ip_network(f"0.0.0.0/{mask}", strict=False).prefixlen)
    except:
        return mask
