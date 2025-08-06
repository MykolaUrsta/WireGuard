from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth import authenticate
from django.utils import timezone
from accounts.models import CustomUser
from .models import UserActionLog, VPNConnectionLog, SecurityEvent
import json
import re
import logging

logger = logging.getLogger(__name__)


class VPNConnectionMiddleware(MiddlewareMixin):
    """Middleware для обробки VPN підключень та логування"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """Обробляємо запити на VPN автентифікацію"""
        
        # Перевіряємо чи це запит від WireGuard для автентифікації
        if request.path.startswith('/accounts/api/vpn/'):
            self._log_vpn_auth_attempt(request)
        
        return None
    
    def process_response(self, request, response):
        """Обробляємо відповіді"""
        
        # Логуємо успішні VPN автентифікації
        if request.path.startswith('/accounts/api/vpn/') and response.status_code == 200:
            try:
                response_data = json.loads(response.content)
                if response_data.get('authenticated'):
                    self._log_successful_vpn_auth(request, response_data)
            except (json.JSONDecodeError, KeyError):
                pass
        
        return response
    
    def _log_vpn_auth_attempt(self, request):
        """Логування спроби VPN автентифікації"""
        try:
            ip_address = self._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Логуємо спробу підключення
            logger.info(f"VPN auth attempt from {ip_address}")
            
        except Exception as e:
            logger.error(f"Error logging VPN auth attempt: {e}")
    
    def _log_successful_vpn_auth(self, request, response_data):
        """Логування успішної VPN автентифікації"""
        try:
            # Отримуємо дані з запиту
            if request.content_type == 'application/json':
                request_data = json.loads(request.body)
                username = request_data.get('username')
                
                if username:
                    user = CustomUser.objects.filter(username=username).first()
                    if user:
                        UserActionLog.objects.create(
                            user=user,
                            action='vpn_connected',
                            ip_address=self._get_client_ip(request),
                            user_agent=request.META.get('HTTP_USER_AGENT', ''),
                            vpn_client_ip=user.wireguard_ip,
                            description='Successful VPN authentication'
                        )
                        
                        # Оновлюємо час останнього VPN підключення
                        user.last_vpn_connection = timezone.now()
                        user.save()
                        
                        logger.info(f"User {username} successfully authenticated for VPN")
        
        except Exception as e:
            logger.error(f"Error logging successful VPN auth: {e}")
    
    def _get_client_ip(self, request):
        """Отримує IP адресу клієнта"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SecurityMiddleware(MiddlewareMixin):
    """Middleware для моніторингу безпеки"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.failed_attempts = {}  # Тимчасове зберігання невдалих спроб
        super().__init__(get_response)
    
    def process_request(self, request):
        """Обробляємо запити для виявлення підозрілої активності"""
        
        ip_address = self._get_client_ip(request)
        
        # Перевіряємо на підозрілі URL
        if self._is_suspicious_request(request):
            self._log_security_event(
                event_type='suspicious_activity',
                severity='medium',
                description=f"Suspicious request to {request.path}",
                ip_address=ip_address,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                additional_data={
                    'path': request.path,
                    'method': request.method,
                    'query_params': dict(request.GET)
                }
            )
        
        return None
    
    def process_response(self, request, response):
        """Обробляємо відповіді для виявлення невдалих автентифікацій"""
        
        # Перевіряємо невдалі спроби входу
        if request.path == reverse('accounts:login') and response.status_code in [200, 302]:
            if hasattr(request, 'user') and not request.user.is_authenticated:
                if request.method == 'POST':
                    self._handle_failed_login(request)
        
        return response
    
    def _is_suspicious_request(self, request):
        """Перевіряє чи є запит підозрілим"""
        suspicious_patterns = [
            r'/admin/',
            r'/wp-admin/',
            r'/phpmyadmin/',
            r'\.php$',
            r'/\.env',
            r'/config\.json',
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, request.path, re.IGNORECASE):
                return True
        
        return False
    
    def _handle_failed_login(self, request):
        """Обробляє невдалі спроби входу"""
        ip_address = self._get_client_ip(request)
        
        # Підраховуємо невдалі спроби
        if ip_address not in self.failed_attempts:
            self.failed_attempts[ip_address] = {'count': 0, 'last_attempt': timezone.now()}
        
        self.failed_attempts[ip_address]['count'] += 1
        self.failed_attempts[ip_address]['last_attempt'] = timezone.now()
        
        # Якщо більше 5 невдалих спроб за 15 хвилин
        if self.failed_attempts[ip_address]['count'] >= 5:
            time_diff = timezone.now() - self.failed_attempts[ip_address]['last_attempt']
            if time_diff.total_seconds() < 900:  # 15 хвилин
                self._log_security_event(
                    event_type='brute_force',
                    severity='high',
                    description=f"Multiple failed login attempts from {ip_address}",
                    ip_address=ip_address,
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    additional_data={
                        'failed_attempts': self.failed_attempts[ip_address]['count'],
                        'time_window': '15 minutes'
                    }
                )
    
    def _log_security_event(self, event_type, severity, description, ip_address=None, user_agent='', additional_data=None):
        """Логує подію безпеки"""
        try:
            SecurityEvent.objects.create(
                event_type=event_type,
                severity=severity,
                description=description,
                ip_address=ip_address,
                user_agent=user_agent,
                additional_data=additional_data or {}
            )
            
            logger.warning(f"Security event: {event_type} - {description}")
            
        except Exception as e:
            logger.error(f"Error logging security event: {e}")
    
    def _get_client_ip(self, request):
        """Отримує IP адресу клієнта"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
