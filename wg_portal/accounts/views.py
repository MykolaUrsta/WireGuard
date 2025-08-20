from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django_otp.decorators import otp_required
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.util import random_hex
import qrcode
from io import BytesIO
import base64
import json
from datetime import timedelta
from .models import CustomUser
from .forms import UserRegistrationForm, UserLoginForm, Enable2FAForm, UserAdminForm, UserFilterForm
from audit_logging.models import UserActionLog
import logging

logger = logging.getLogger(__name__)


class LoginView(View):
    """Вхід користувача з підтримкою 2FA"""
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('accounts:dashboard')
        form = UserLoginForm()
        return render(request, 'accounts/login.html', {'form': form})
    
    def post(self, request):
        form = UserLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            
            user = authenticate(request, username=email, password=password)
            if user is not None:
                if user.is_2fa_enabled:
                    # Зберігаємо користувача в сесії для 2FA
                    request.session['pre_2fa_user_id'] = user.id
                    return redirect('verify_2fa')
                else:
                    login(request, user)
                    logger.info(f"Користувач {user.username} увійшов в систему")
                    UserActionLog.objects.create(
                        user=user,
                        action='login',
                        ip_address=request.META.get('REMOTE_ADDR'),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')
                    )
                    return redirect('accounts:dashboard')
            else:
                messages.error(request, 'Невірний email або пароль')
        
        return render(request, 'accounts/login.html', {'form': form})


class Verify2FAView(View):
    """Перевірка 2FA коду"""
    
    def get(self, request):
        if 'pre_2fa_user_id' not in request.session:
            return redirect('login')
        return render(request, 'accounts/verify_2fa.html')
    
    def post(self, request):
        if 'pre_2fa_user_id' not in request.session:
            return redirect('login')
        
        user_id = request.session['pre_2fa_user_id']
        user = CustomUser.objects.get(id=user_id)
        token = request.POST.get('token', '').strip()
        
        if not token:
            messages.error(request, 'Введіть код автентифікації')
            return render(request, 'accounts/verify_2fa.html')
        
        # Перевіряємо TOTP код
        device = TOTPDevice.objects.filter(user=user, confirmed=True).first()
        if device and device.verify_token(token):
            login(request, user)
            del request.session['pre_2fa_user_id']
            logger.info(f"Користувач {user.username} пройшов 2FA автентифікацію")
            UserActionLog.objects.create(
                user=user,
                action='2fa_success',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return redirect('accounts:dashboard')
        else:
            messages.error(request, 'Невірний код автентифікації')
            UserActionLog.objects.create(
                user=user,
                action='2fa_failed',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
        
        return render(request, 'accounts/verify_2fa.html')


@login_required
def vpn_overview(request):
    """VPN Overview - головна сторінка з статистикою мережі"""
    from wireguard_management.models import WireGuardPeer, WireGuardNetwork, WireGuardServer
    from audit_logging.models import VPNConnectionLog, UserActionLog
    from django.db.models import Count, Q
    from django.utils import timezone
    from datetime import timedelta
    
    # Статистика підключень
    total_peers = WireGuardPeer.objects.count()
    active_connections = WireGuardPeer.objects.filter(is_active=True).count()
    
    # Статистика за 24 години
    last_24h = timezone.now() - timedelta(hours=24)
    connections_24h = VPNConnectionLog.objects.filter(
        connect_time__gte=last_24h
    ).count()
    
    # Навантаження мережі (умовно)
    network_load = min(85, (active_connections / max(total_peers, 1)) * 100)
    
    # Активні користувачі з детальною інформацією - тільки дійсно онлайн користувачі
    connected_users = WireGuardPeer.objects.filter(
        is_active=True,
        last_handshake__gte=timezone.now() - timedelta(seconds=180)
    ).select_related('user', 'server').order_by('-last_handshake')[:10]
    
    # Активність користувачів
    recent_activity = UserActionLog.objects.filter(
        timestamp__gte=last_24h
    ).select_related('user').order_by('-timestamp')[:15]
    
    # Статистика трафіку
    total_traffic_in = sum(peer.bytes_received or 0 for peer in WireGuardPeer.objects.all())
    total_traffic_out = sum(peer.bytes_sent or 0 for peer in WireGuardPeer.objects.all())
    
    context = {
        'user': request.user,
        # Основна статистика
        'active_connections': active_connections,
        'connections_24h': connections_24h,
        'network_load': round(network_load),
        'total_peers': total_peers,
        
        # Трафік
        'traffic_in_mb': round(total_traffic_in / (1024 * 1024), 1) if total_traffic_in else 0,
        'traffic_out_mb': round(total_traffic_out / (1024 * 1024), 1) if total_traffic_out else 0,
        
        # Підключені користувачі
        'connected_users': connected_users,
        'recent_activity': recent_activity,
        
        # Мережі та сервери
        'networks': WireGuardNetwork.objects.all()[:5],
        'servers': WireGuardServer.objects.all()[:5],
    }
    return render(request, 'accounts/vpn_overview.html', context)


@login_required
def connected_users_api(request):
    """API для отримання списку підключених користувачів"""
    from locations.models import Device
    from django.http import JsonResponse
    from django.utils import timezone
    
    # Отримуємо тільки дійсно онлайн користувачів
    all_devices = Device.objects.filter(
        status='active'
    ).select_related('user', 'location').order_by('-last_handshake')
    
    # Фільтруємо тільки активні пристрої (з handshake менше 5 хвилин тому)
    connected_devices = [device for device in all_devices if device.is_online]
    
    users_data = []
    for device in connected_devices:
        # Розраховуємо час підключення
        connection_time = device.get_connection_time_formatted() if hasattr(device, 'get_connection_time_formatted') else "00:00"
        
        users_data.append({
            'id': device.id,
            'username': device.user.username,
            'full_name': device.user.get_full_name() or device.user.username,
            'device_name': device.name,
            'ip_address': device.ip_address,
            'location_name': device.location.name if device.location else 'Unknown',
            'connection_time': connection_time,
            'bytes_sent': device.bytes_sent or 0,
            'bytes_received': device.bytes_received or 0,
            'last_handshake': device.last_handshake.isoformat() if device.last_handshake else None,
            'avatar_initials': (device.user.first_name[:1] + device.user.last_name[:1]).upper() if device.user.first_name and device.user.last_name else device.user.username[:1].upper()
        })
    
    return JsonResponse({'users': users_data})


@login_required
def setup_2fa(request):
    """Налаштування двофакторної автентифікації"""
    if request.user.is_2fa_enabled:
        messages.info(request, '2FA вже увімкнена')
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        device_name = request.POST.get('device_name', 'Мобільний пристрій')
        
        if not token:
            messages.error(request, 'Введіть код з додатка автентифікації')
            return redirect('setup_2fa')
        
        # Отримуємо або створюємо TOTP пристрій
        device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
        if not device:
            device = TOTPDevice.objects.create(
                user=request.user,
                name=device_name,
                confirmed=False
            )
        
        if device.verify_token(token):
            device.confirmed = True
            device.save()
            request.user.is_2fa_enabled = True
            request.user.save()
            
            messages.success(request, '2FA успішно налаштована!')
            logger.info(f"Користувач {request.user.username} увімкнув 2FA")
            UserActionLog.objects.create(
                user=request.user,
                action='2fa_enabled',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return redirect('accounts:dashboard')
        else:
            messages.error(request, 'Невірний код автентифікації')
    
    # Створюємо новий непідтверджений пристрій
    device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
    if not device:
        device = TOTPDevice.objects.create(
            user=request.user,
            name='Мобільний пристрій',
            confirmed=False
        )
    
    # Генеруємо QR код
    qr_url = device.config_url
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    qr_image = base64.b64encode(buffer.getvalue()).decode()
    
    context = {
        'qr_image': qr_image,
        'secret_key': device.bin_key,
        'qr_url': qr_url
    }
    
    return render(request, 'accounts/setup_2fa.html', context)


@login_required
def disable_2fa(request):
    """Вимкнення 2FA"""
    if request.method == 'POST':
        password = request.POST.get('password')
        user = authenticate(username=request.user.email, password=password)
        
        if user:
            # Видаляємо всі TOTP пристрої
            TOTPDevice.objects.filter(user=request.user).delete()
            request.user.is_2fa_enabled = False
            request.user.save()
            
            messages.success(request, '2FA вимкнена')
            logger.info(f"Користувач {request.user.username} вимкнув 2FA")
            UserActionLog.objects.create(
                user=request.user,
                action='2fa_disabled',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
        else:
            messages.error(request, 'Невірний пароль')
    
    return render(request, 'accounts/disable_2fa.html')


def logout_view(request):
    """Вихід користувача"""
    if request.user.is_authenticated:
        logger.info(f"Користувач {request.user.username} вийшов з системи")
        UserActionLog.objects.create(
            user=request.user,
            action='logout',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
    logout(request)
    return redirect('login')


@csrf_exempt
@require_http_methods(["POST"])
def vpn_auth_check(request):
    """API endpoint для перевірки автентифікації при підключенні до VPN"""
    try:
        data = json.loads(request.body)
        username = data.get('username')
        public_key = data.get('public_key')
        
        if not username or not public_key:
            return JsonResponse({'authenticated': False, 'message': 'Відсутні дані'})
        
        user = CustomUser.objects.filter(username=username).first()
        if not user or not user.is_wireguard_enabled:
            return JsonResponse({'authenticated': False, 'message': 'Користувач не авторизований'})
        
        if user.wireguard_public_key != public_key:
            return JsonResponse({'authenticated': False, 'message': 'Невірний публічний ключ'})
        
        # Якщо у користувача увімкнена 2FA, потрібна додаткова перевірка
        if user.is_2fa_enabled:
            return JsonResponse({
                'authenticated': False, 
                'requires_2fa': True,
                'user_id': user.id,
                'message': 'Потрібна 2FA автентифікація'
            })
        
        return JsonResponse({'authenticated': True, 'message': 'Автентифікація успішна'})
        
    except Exception as e:
        logger.error(f"Помилка при VPN автентифікації: {e}")
        return JsonResponse({'authenticated': False, 'message': 'Помилка сервера'})


@csrf_exempt
@require_http_methods(["POST"])
def vpn_2fa_verify(request):
    """API endpoint для перевірки 2FA при підключенні до VPN"""
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        token = data.get('token')
        
        if not user_id or not token:
            return JsonResponse({'authenticated': False, 'message': 'Відсутні дані'})
        
        user = CustomUser.objects.filter(id=user_id).first()
        if not user:
            return JsonResponse({'authenticated': False, 'message': 'Користувач не знайдений'})
        
        device = TOTPDevice.objects.filter(user=user, confirmed=True).first()
        if device and device.verify_token(token):
            logger.info(f"Користувач {user.username} пройшов VPN 2FA автентифікацію")
            UserActionLog.objects.create(
                user=user,
                action='vpn_2fa_success',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return JsonResponse({'authenticated': True, 'message': '2FA перевірка успішна'})
        else:
            UserActionLog.objects.create(
                user=user,
                action='vpn_2fa_failed',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return JsonResponse({'authenticated': False, 'message': 'Невірний 2FA код'})
        
    except Exception as e:
        logger.error(f"Помилка при VPN 2FA перевірці: {e}")
        return JsonResponse({'authenticated': False, 'message': 'Помилка сервера'})


class RegistrationView(View):
    """Реєстрація нового користувача"""
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('accounts:dashboard')
        form = UserRegistrationForm()
        return render(request, 'accounts/register.html', {'form': form})
    
    def post(self, request):
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Реєстрація успішна! Увійдіть в систему.')
            logger.info(f"Новий користувач зареєстрований: {user.username}")
            UserActionLog.objects.create(
                user=user,
                action='register',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return redirect('login')
        
        return render(request, 'accounts/register.html', {'form': form})


@login_required
def users_list(request):
    """Список всіх користувачів системи з фільтрацією"""
    from django.contrib.auth import get_user_model
    from django.core.paginator import Paginator
    from django.db.models import Q
    
    User = get_user_model()
    
    # Форма фільтрації
    filter_form = UserFilterForm(request.GET)
    users = User.objects.all()
    
    # Застосування фільтрів
    if filter_form.is_valid():
        filter_type = filter_form.cleaned_data.get('filter_type', 'all')
        search_query = filter_form.cleaned_data.get('search', '')
        
        # Фільтрація за типом
        if filter_type == 'active':
            users = users.filter(is_active=True)
        elif filter_type == 'inactive':
            users = users.filter(is_active=False)
        elif filter_type == 'admin':
            users = users.filter(is_superuser=True)
        elif filter_type == 'staff':
            users = users.filter(is_staff=True)
        elif filter_type == 'wireguard_enabled':
            users = users.filter(is_wireguard_enabled=True)
        elif filter_type == 'wireguard_disabled':
            users = users.filter(is_wireguard_enabled=False)
        
        # Пошук
        if search_query:
            users = users.filter(
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(phone__icontains=search_query)
            )
    
    # Сортування
    sort_by = request.GET.get('sort', 'username')
    users = users.order_by(sort_by)
    
    # Пагінація
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Статистика для фільтрів
    filter_stats = {
        'all': User.objects.count(),
        'active': User.objects.filter(is_active=True).count(),
        'inactive': User.objects.filter(is_active=False).count(),
        'admin': User.objects.filter(is_superuser=True).count(),
        'staff': User.objects.filter(is_staff=True).count(),
        'wireguard_enabled': User.objects.filter(is_wireguard_enabled=True).count(),
        'wireguard_disabled': User.objects.filter(is_wireguard_enabled=False).count(),
    }
    
    context = {
        'users': page_obj,
        'filter_form': filter_form,
        'filter_stats': filter_stats,
        'total_users': users.count(),
        'sort_by': sort_by,
    }
    
    return render(request, 'accounts/users_list.html', context)


@login_required
def user_add(request):
    """Додавання нового користувача"""
    if not request.user.is_staff:
        messages.error(request, 'У вас немає прав для додавання користувачів')
        return redirect('accounts:users_list')
    
    if request.method == 'POST':
        form = UserAdminForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Користувач {user.username} успішно створений')
            logger.info(f"Адміністратор {request.user.username} створив користувача {user.username}")
            UserActionLog.objects.create(
                user=request.user,
                action='user_created',
                description=f'Створено користувача {user.username}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return redirect('accounts:users_list')
    else:
        form = UserAdminForm()
    
    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': 'Додати користувача',
        'submit_text': 'Створити користувача'
    })


@login_required
def user_edit(request, pk):
    """Редагування користувача"""
    if not request.user.is_staff:
        messages.error(request, 'У вас немає прав для редагування користувачів')
        return redirect('accounts:users_list')
    
    from django.shortcuts import get_object_or_404
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    user = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        form = UserAdminForm(request.POST, instance=user)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Користувач {user.username} успішно оновлений')
            logger.info(f"Адміністратор {request.user.username} оновив користувача {user.username}")
            UserActionLog.objects.create(
                user=request.user,
                action='user_updated',
                description=f'Оновлено користувача {user.username}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return redirect('accounts:users_list')
    else:
        form = UserAdminForm(instance=user)
    
    return render(request, 'accounts/user_form.html', {
        'form': form,
        'user_obj': user,
        'title': f'Редагувати {user.username}',
        'submit_text': 'Зберегти зміни'
    })


@login_required
def user_delete(request, pk):
    """Видалення користувача"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас немає прав для видалення користувачів')
        return redirect('accounts:users_list')
    
    from django.shortcuts import get_object_or_404
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    user = get_object_or_404(User, pk=pk)
    
    if user == request.user:
        messages.error(request, 'Ви не можете видалити себе')
        return redirect('accounts:users_list')
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'Користувач {username} успішно видалений')
        logger.info(f"Адміністратор {request.user.username} видалив користувача {username}")
        UserActionLog.objects.create(
            user=request.user,
            action='user_deleted',
            description=f'Видалено користувача {username}',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        return redirect('accounts:users_list')
    
    return render(request, 'accounts/user_confirm_delete.html', {
        'user_obj': user
    })


@login_required
@require_http_methods(["POST"])
def user_toggle_active(request, pk):
    """Активація/деактивація користувача"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Немає прав'})
    
    from django.shortcuts import get_object_or_404
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    user = get_object_or_404(User, pk=pk)
    
    if user == request.user:
        return JsonResponse({'success': False, 'error': 'Ви не можете деактивувати себе'})
    
    user.is_active = not user.is_active
    user.save()
    
    action = 'user_activated' if user.is_active else 'user_deactivated'
    status = 'активовано' if user.is_active else 'деактивовано'
    
    logger.info(f"Адміністратор {request.user.username} {status} користувача {user.username}")
    UserActionLog.objects.create(
        user=request.user,
        action=action,
        description=f'{status.capitalize()} користувача {user.username}',
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    return JsonResponse({
        'success': True,
        'is_active': user.is_active,
        'message': f'Користувач {user.username} {status}'
    })


@login_required
def user_detail(request, pk):
    """Детальний перегляд профілю користувача"""
    from django.contrib.auth import get_user_model
    from locations.models import Device
    from django.utils import timezone
    from datetime import timedelta
    
    User = get_user_model()
    user = get_object_or_404(User, pk=pk)
    
    # Отримуємо пристрої користувача
    devices = Device.objects.filter(user=user).select_related('location', 'network', 'group')
    
    # Підраховуємо статистику по пристроях
    total_devices = devices.count()
    active_devices = devices.filter(status='active').count()
    connected_devices = devices.filter(
        last_handshake__gte=timezone.now() - timedelta(minutes=10)
    ).count()
    
    # Загальна статистика трафіку
    total_upload = sum(device.bytes_sent or 0 for device in devices)
    total_download = sum(device.bytes_received or 0 for device in devices)
    
    # Перевіряємо 2FA статус
    from django_otp.plugins.otp_totp.models import TOTPDevice
    totp_devices = TOTPDevice.objects.filter(user=user, confirmed=True)
    has_2fa = totp_devices.exists()
    
    # Форматуємо дані для кожного пристрою
    device_data = []
    for device in devices:
        # Визначаємо статус підключення
        is_connected = False
        connection_status = "Never connected"
        if device.last_handshake:
            time_diff = timezone.now() - device.last_handshake
            if time_diff < timedelta(minutes=10):
                is_connected = True
                connection_status = "Connected"
            else:
                connection_status = f"Last seen {time_diff.days} days ago" if time_diff.days > 0 else "Recently disconnected"
        
        device_data.append({
            'device': device,
            'is_connected': is_connected,
            'connection_status': connection_status,
            'public_ip': device.location.server_ip if device.location else None,
            'config_generated': bool(device.public_key and device.private_key),
        })
    
    context = {
        'profile_user': user,  # Renamed to avoid conflict with request.user
        'devices': device_data,
        'total_devices': total_devices,
        'active_devices': active_devices,
        'connected_devices': connected_devices,
        'total_upload': total_upload,
        'total_download': total_download,
        'has_2fa': has_2fa,
        'can_edit': request.user.is_staff or request.user == user,
    }
    
    return render(request, 'accounts/user_detail.html', context)


@login_required
def device_config_modal(request, device_id):
    """API для отримання конфігурації пристрою та QR-коду"""
    from locations.models import Device
    from django.http import JsonResponse
    import qrcode
    import io
    import base64
    
    device = get_object_or_404(Device, pk=device_id)
    
    # Перевіряємо права доступу
    if request.user != device.user and not request.user.is_staff:
        return JsonResponse({'error': 'Немає прав доступу'}, status=403)
    
    try:
        # Генеруємо конфігурацію
        config_content = device.get_config()
        
        # Створюємо QR-код
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(config_content)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Конвертуємо в base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return JsonResponse({
            'device_name': device.name,
            'config': config_content,
            'qr_code': f"data:image/png;base64,{img_str}",
            'device_ip': device.ip_address,
            'server_endpoint': f"{device.location.server_ip}:{device.location.server_port}",
            'connection_time': device.get_connection_time_formatted() if hasattr(device, 'get_connection_time_formatted') else '00:00',
            'bytes_sent': device.bytes_sent or 0,
            'bytes_received': device.bytes_received or 0,
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Помилка генерації конфігурації: {str(e)}'}, status=500)


@login_required
def device_delete(request, device_id):
    """Видалення пристрою"""
    from locations.models import Device
    from django.http import JsonResponse
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Тільки POST запити'}, status=405)
    
    device = get_object_or_404(Device, pk=device_id)
    
    # Перевіряємо права доступу
    if request.user != device.user and not request.user.is_staff:
        return JsonResponse({'error': 'Немає прав доступу'}, status=403)
    
    try:
        device_name = device.name
        location = device.location
        
        # Видаляємо пристрій
        device.delete()
        
        # Оновлюємо конфігурацію WireGuard
        try:
            from locations.docker_manager import WireGuardDockerManager
            manager = WireGuardDockerManager()
            manager.generate_server_config(location)
        except Exception as config_error:
            # Логуємо помилку, але не зупиняємо видалення
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Помилка оновлення WireGuard конфігурації після видалення пристрою: {config_error}")
        
        return JsonResponse({
            'success': True,
            'message': f'Пристрій "{device_name}" видалено успішно'
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Помилка видалення: {str(e)}'}, status=500)


@login_required
def user_devices_api(request, user_id):
    """API для отримання списку пристроїв користувача (для real-time оновлення)"""
    from locations.models import Device
    from django.http import JsonResponse
    from django.utils import timezone
    from datetime import timedelta
    
    user = get_object_or_404(get_user_model(), pk=user_id)
    
    # Перевіряємо права доступу
    if request.user != user and not request.user.is_staff:
        return JsonResponse({'error': 'Немає прав доступу'}, status=403)
    
    devices = Device.objects.filter(user=user).select_related('location', 'network')
    
    devices_data = []
    for device in devices:
        # Розраховуємо час підключення
        connection_time = "00:00"
        is_connected = False
        
        if device.connected_at and device.last_handshake:
            time_diff = timezone.now() - device.last_handshake
            if time_diff < timedelta(minutes=3):  # Онлайн якщо handshake менше 3 хвилин тому
                is_connected = True
                if device.connected_at:
                    duration = int((timezone.now() - device.connected_at).total_seconds())
                    hours = duration // 3600
                    minutes = (duration % 3600) // 60
                    seconds = duration % 60
                    
                    if hours > 0:
                        connection_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    else:
                        connection_time = f"{minutes:02d}:{seconds:02d}"
        
        # Статус підключення
        if is_connected:
            connection_status = "Connected"
        elif device.last_handshake:
            time_diff = timezone.now() - device.last_handshake
            if time_diff.days > 0:
                connection_status = f"Last seen {time_diff.days} days ago"
            else:
                connection_status = "Disconnected"
        else:
            connection_status = "Never connected"
        
        devices_data.append({
            'id': device.id,
            'name': device.name,
            'ip_address': device.ip_address,
            'is_connected': is_connected,
            'connection_status': connection_status,
            'connection_time': connection_time,
            'bytes_sent': device.bytes_sent or 0,
            'bytes_received': device.bytes_received or 0,
            'last_handshake': device.last_handshake.isoformat() if device.last_handshake else None,
            'public_ip': device.location.server_ip if device.location else None,
        })
    
    return JsonResponse({'devices': devices_data})
