from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django_otp.decorators import otp_required
from django_otp.models import Device
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.util import random_hex
import qrcode
from io import BytesIO
import base64
import json
from .models import CustomUser
from .forms import UserRegistrationForm, UserLoginForm, Enable2FAForm
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
    
    # Активні користувачі з детальною інформацією
    connected_users = WireGuardPeer.objects.filter(
        is_active=True
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
