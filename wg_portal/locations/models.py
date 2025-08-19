# locations/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import validate_ipv4_address, RegexValidator
from django.core.exceptions import ValidationError
import ipaddress

User = get_user_model()


class Location(models.Model):
    """Локація WireGuard (аналог Defguard Location)"""
    name = models.CharField(
        max_length=100, 
        unique=True,
        verbose_name="Назва локації"
    )
    description = models.TextField(
        blank=True, 
        verbose_name="Опис"
    )
    server_ip = models.GenericIPAddressField(
        protocol='IPv4',
        verbose_name="IP сервера",
        help_text="Зовнішній IP адрес WireGuard сервера"
    )
    server_port = models.PositiveIntegerField(
        default=51820,
        verbose_name="Порт сервера",
        help_text="UDP порт WireGuard сервера"
    )
    subnet = models.CharField(
        max_length=18,
        verbose_name="Підмережа",
        help_text="Приватна підмережа (наприклад: 10.13.13.0/24)",
        validators=[
            RegexValidator(
                regex=r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$',
                message='Введіть правильну підмережу у форматі CIDR (наприклад: 10.13.13.0/24)'
            )
        ]
    )
    interface_name = models.CharField(
        max_length=15,
        default='wg0',
        verbose_name="Ім'я інтерфейсу",
        validators=[
            RegexValidator(
                regex=r'^wg\d+$',
                message="Ім'я інтерфейсу повинно мати формат wgX (наприклад: wg0, wg1)"
            )
        ]
    )
    public_key = models.CharField(
        max_length=44,
        blank=True,
        verbose_name="Публічний ключ",
        help_text="Публічний ключ WireGuard сервера"
    )
    private_key = models.CharField(
        max_length=44,
        blank=True,
        verbose_name="Приватний ключ",
        help_text="Приватний ключ WireGuard сервера"
    )
    dns_servers = models.CharField(
        max_length=255,
        default="1.1.1.1,8.8.8.8",
        verbose_name="DNS сервери",
        help_text="DNS сервери через кому"
    )
    allowed_ips = models.CharField(
        max_length=255,
        default="0.0.0.0/0",
        verbose_name="Дозволені IP/мережі",
        help_text="Список дозволених IP адрес або мереж через кому (наприклад: 0.0.0.0/0 для всього трафіку, або 192.168.1.0/24,10.0.0.0/8)"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активна"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Створено"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Оновлено"
    )

    class Meta:
        verbose_name = "Локація"
        verbose_name_plural = "Локації"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.subnet})"

    def clean(self):
        """Валідація IP підмережі"""
        try:
            network = ipaddress.IPv4Network(self.subnet, strict=False)
            self.subnet = str(network)
        except ValueError:
            raise ValidationError({'subnet': 'Невірний формат підмережі'})
        
        # Автоматично призначаємо інтерфейс якщо не вказаний
        if not self.interface_name or self.interface_name == 'wg0':
            self.interface_name = self.get_next_available_interface()

    @classmethod
    def get_next_available_interface(cls):
        """Повертає наступний доступний WireGuard інтерфейс"""
        existing_interfaces = set(
            cls.objects.values_list('interface_name', flat=True)
        )
        
        for i in range(100):  # Максимум 100 інтерфейсів
            interface = f'wg{i}'
            if interface not in existing_interfaces:
                return interface
        
        return 'wg0'  # Fallback

    @property
    def network(self):
        """Повертає об'єкт IPv4Network"""
        return ipaddress.IPv4Network(self.subnet, strict=False)

    @property
    def gateway_ip(self):
        """IP адреса шлюзу (перший адрес в підмережі)"""
        return str(list(self.network.hosts())[0])

    @property
    def next_available_ip(self):
        """Наступний доступний IP в підмережі"""
        used_ips = set(
            Device.objects.filter(location=self)
            .values_list('ip_address', flat=True)
        )
        used_ips.add(self.gateway_ip)
        
        for ip in self.network.hosts():
            if str(ip) not in used_ips:
                return str(ip)
        return None

    def save(self, *args, **kwargs):
        """Зберігає локацію та оновлює WireGuard конфігурацію"""
        is_new = self.pk is None
        
        # Генеруємо ключі якщо їх немає
        if not self.private_key or not self.public_key:
            self._generate_keys()
        
        # Спочатку зберігаємо модель
        super().save(*args, **kwargs)
        
        # Створюємо дефолтну мережу для нової локації
        if is_new:
            self._create_default_network()
        
        # Потім оновлюємо WireGuard конфігурацію
        if self.is_active:
            try:
                from .docker_manager import WireGuardDockerManager
                manager = WireGuardDockerManager()
                
                # Генеруємо конфігурацію для цієї локації
                manager.generate_server_config(self)
                # Генеруємо конфігурації для всіх активних локацій
                manager.generate_all_active_configs()
                # Перезапускаємо цей інтерфейс
                manager.restart_wireguard(self.interface_name)
                
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Помилка оновлення WireGuard конфігурації для локації {self.name}: {str(e)}")

    def _generate_keys(self):
        """Генерує приватний та публічний ключі WireGuard"""
        try:
            import subprocess
            
            # Генеруємо приватний ключ
            private_key_result = subprocess.run(
                ['wg', 'genkey'], 
                capture_output=True, 
                text=True, 
                check=True
            )
            self.private_key = private_key_result.stdout.strip()
            
            # Генеруємо публічний ключ
            public_key_result = subprocess.run(
                ['wg', 'pubkey'], 
                input=self.private_key,
                capture_output=True, 
                text=True, 
                check=True
            )
            self.public_key = public_key_result.stdout.strip()
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Якщо wg недоступний, генеруємо фейкові ключі для розробки
            import secrets
            import base64
            
            # Генеруємо 32 байти для ключа
            private_bytes = secrets.token_bytes(32)
            self.private_key = base64.b64encode(private_bytes).decode('ascii')
            
            public_bytes = secrets.token_bytes(32)
            self.public_key = base64.b64encode(public_bytes).decode('ascii')

    def _create_default_network(self):
        """Створює дефолтну мережу для нової локації"""
        try:
            from .models import Network
            
            # Перевіряємо чи немає вже мережі
            if self.networks.exists():
                return
            
            Network.objects.create(
                name=f"{self.name} - Default Network",
                location=self,
                subnet=self.subnet,
                interface=self.interface_name,
                server_port=self.server_port,
                listen_port=self.server_port,
                server_public_key=self.public_key,
                server_ip=self.server_ip,
                allowed_ips=self.allowed_ips or "0.0.0.0/0",
                dns_servers=self.dns_servers,
                is_active=True
            )
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Помилка створення дефолтної мережі: {str(e)}")


class DeviceGroup(models.Model):
    """Група пристроїв для ACL"""
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Назва групи"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Опис"
    )
    color = models.CharField(
        max_length=7,
        default="#6366f1",
        verbose_name="Колір",
        help_text="Hex колір для відображення"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Створено"
    )

    class Meta:
        verbose_name = "Група пристроїв"
        verbose_name_plural = "Групи пристроїв"
        ordering = ['name']

    def __str__(self):
        return self.name


class Network(models.Model):
    """Модель мережі WireGuard"""
    name = models.CharField(
        max_length=100,
        verbose_name="Назва мережі"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='networks',
        verbose_name="Локація"
    )
    subnet = models.CharField(
        max_length=18,
        verbose_name="Підмережа",
        help_text="Наприклад: 10.13.13.0/24"
    )
    interface = models.CharField(
        max_length=50,
        default='wg0',
        verbose_name="Інтерфейс",
        help_text="Назва WireGuard інтерфейсу"
    )
    server_port = models.PositiveIntegerField(
        default=51820,
        verbose_name="Порт сервера",
        help_text="UDP порт WireGuard сервера"
    )
    listen_port = models.PositiveIntegerField(
        default=51820,
        verbose_name="Порт прослуховування",
        help_text="UDP порт WireGuard для прослуховування"
    )
    server_public_key = models.CharField(
        max_length=44,
        verbose_name="Публічний ключ сервера",
        help_text="WireGuard публічний ключ сервера"
    )
    server_ip = models.GenericIPAddressField(
        protocol='IPv4',
        verbose_name="IP сервера",
        help_text="IP адреса сервера в мережі",
        null=True,
        blank=True
    )
    allowed_ips = models.CharField(
        max_length=255,
        default="0.0.0.0/0",
        verbose_name="Дозволені IP",
        help_text="Список дозволених IP адрес або підмереж"
    )
    dns_servers = models.CharField(
        max_length=255,
        default="1.1.1.1,8.8.8.8",
        verbose_name="DNS сервери"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активна"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Створено"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Оновлено"
    )

    class Meta:
        verbose_name = "Мережа"
        verbose_name_plural = "Мережі"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.subnet})"

    def save(self, *args, **kwargs):
        """Зберігає мережу та оновлює WireGuard конфігурацію"""
        # Спочатку зберігаємо модель
        super().save(*args, **kwargs)
        
        # Оновлюємо WireGuard конфігурацію для пов'язаної локації
        if self.location and self.location.is_active and self.is_active:
            try:
                from .docker_manager import WireGuardDockerManager
                manager = WireGuardDockerManager()
                
                # Генеруємо конфігурацію для локації цієї мережі
                manager.generate_server_config(self.location)
                # Перезапускаємо інтерфейс
                manager.restart_wireguard(self.location.interface_name)
                
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Помилка оновлення WireGuard конфігурації для мережі {self.name}: {str(e)}")


class AccessControlList(models.Model):
    """Список контролю доступу (ACL)"""
    name = models.CharField(
        max_length=100,
        verbose_name="Назва ACL"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Опис"
    )
    network = models.ForeignKey(
        Network,
        on_delete=models.CASCADE,
        related_name='acl_rules',
        verbose_name="Мережа"
    )
    source_groups = models.ManyToManyField(
        DeviceGroup,
        related_name='source_acl_rules',
        blank=True,
        verbose_name="Вихідні групи"
    )
    destination_groups = models.ManyToManyField(
        DeviceGroup,
        related_name='destination_acl_rules',
        blank=True,
        verbose_name="Цільові групи"
    )
    protocol = models.CharField(
        max_length=10,
        choices=[
            ('tcp', 'TCP'),
            ('udp', 'UDP'),
            ('icmp', 'ICMP'),
            ('all', 'Всі'),
        ],
        default='all',
        verbose_name="Протокол"
    )
    port_ranges = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Діапазони портів",
        help_text="Наприклад: 80,443,8000-9000"
    )
    action = models.CharField(
        max_length=10,
        choices=[
            ('allow', 'Дозволити'),
            ('deny', 'Заборонити'),
        ],
        default='allow',
        verbose_name="Дія"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активне"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Створено"
    )

    class Meta:
        verbose_name = "Правило ACL"
        verbose_name_plural = "Правила ACL"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.action})"


class Device(models.Model):
    """Пристрій користувача в WireGuard мережі"""
    STATUS_CHOICES = [
        ('active', 'Активний'),
        ('inactive', 'Неактивний'),
        ('blocked', 'Заблокований'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='devices',
        verbose_name="Користувач"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='devices',
        verbose_name="Локація"
    )
    network = models.ForeignKey(
        Network,
        on_delete=models.CASCADE,
        related_name='devices',
        verbose_name="Мережа",
        null=True,
        blank=True
    )
    group = models.ForeignKey(
        DeviceGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='devices',
        verbose_name="Група"
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Назва пристрою",
        help_text="Наприклад: iPhone, Laptop, etc."
    )
    description = models.TextField(
        blank=True,
        verbose_name="Опис"
    )
    ip_address = models.GenericIPAddressField(
        protocol='IPv4',
        verbose_name="IP адреса",
        help_text="IP адреса в підмережі локації"
    )
    public_key = models.CharField(
        max_length=44,
        unique=True,
        verbose_name="Публічний ключ"
    )
    private_key = models.CharField(
        max_length=44,
        verbose_name="Приватний ключ"
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name="Статус"
    )
    last_handshake = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Час підключення",
        help_text="Час останнього активного підключення (оновлюється при трафіку)"
    )
    connected_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Початковий час підключення",
        help_text="Час першого підключення в сесії"
    )
    bytes_sent = models.BigIntegerField(
        default=0,
        verbose_name="Відправлено байт"
    )
    bytes_received = models.BigIntegerField(
        default=0,
        verbose_name="Отримано байт"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Створено"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Оновлено"
    )

    class Meta:
        verbose_name = "Пристрій"
        verbose_name_plural = "Пристрої"
        unique_together = [['user', 'location', 'name']]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.name} ({self.ip_address})"

    @property
    def is_online(self):
        """Чи пристрій онлайн (на основі last_handshake як часу підключення)"""
        if self.status != 'active':
            return False
        # last_handshake показує час підключення
        # Якщо немає трафіку протягом 1 хвилини - пристрій вважається відключеним
        if not self.last_handshake:
            return False
        from django.utils import timezone
        # Перевіряємо, чи був трафік протягом останньої 1 хвилини
        time_since_handshake = (timezone.now() - self.last_handshake).total_seconds()
        return time_since_handshake < 60  # 1 хвилина

    @property
    def is_connected(self):
        """Псевдонім для is_online для сумісності"""
        return self.is_online

    @property
    def traffic_total(self):
        """Загальний трафік"""
        return self.bytes_sent + self.bytes_received
    
    def update_traffic(self, bytes_sent, bytes_received):
        """Оновлює трафік. last_handshake та connected_at оновлюються тільки в celery тасці."""
        self.bytes_sent = bytes_sent
        self.bytes_received = bytes_received
    
    def get_connection_time_formatted(self):
        """Повертає відформатований час підключення на основі last_handshake"""
        if not self.last_handshake or not self.is_online:
            return "00:00"
        
        from django.utils import timezone
        duration = int((timezone.now() - self.last_handshake).total_seconds())
        
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    def generate_config(self):
        """Генерує конфігурацію WireGuard для пристрою"""
        return self.get_config()

    def get_config(self):
        """Генерує конфігурацію WireGuard для пристрою"""
        import ipaddress
        
        # Отримуємо мережу та її параметри
        network = self.network
        if not network:
            return "# Error: No network assigned to device"
        
        # Розрахунок маски підмережі
        network_ip = ipaddress.IPv4Network(network.subnet)
        
        config = f"""[Interface]
PrivateKey = {self.private_key if self.private_key else 'YOUR_PRIVATE_KEY'}
Address = {self.ip_address}/{network_ip.prefixlen}
DNS = {network.dns_servers or '8.8.8.8, 8.8.4.4'}

[Peer]
PublicKey = {network.server_public_key}
Endpoint = {self.location.server_ip}:{network.listen_port}
AllowedIPs = {self.location.allowed_ips or '0.0.0.0/0'}
PersistentKeepalive = 25
"""
        return config

    def save(self, *args, **kwargs):
        """Зберігає пристрій та оновлює WireGuard конфігурацію"""
        is_new = self.pk is None
        old_device = None
        
        # Якщо це оновлення, зберігаємо старі дані
        if not is_new:
            try:
                old_device = Device.objects.get(pk=self.pk)
            except Device.DoesNotExist:
                pass
        
        # Зберігаємо модель
        super().save(*args, **kwargs)
        
        # Оновлюємо WireGuard конфігурацію
        try:
            from .docker_manager import WireGuardDockerManager
            manager = WireGuardDockerManager()
            
            if self.status == 'active' and self.public_key:
                # Додаємо або оновлюємо peer
                manager.add_peer_to_server(self)
            elif old_device and old_device.public_key:
                # Видаляємо старий peer якщо пристрій деактивований
                manager.remove_peer_from_server(old_device)
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Помилка оновлення WireGuard peer для пристрою {self.name}: {str(e)}")

    def delete(self, *args, **kwargs):
        """Видаляє пристрій та прибирає його з WireGuard конфігурації"""
        try:
            from .docker_manager import WireGuardDockerManager
            manager = WireGuardDockerManager()
            
            # Видаляємо peer з сервера
            if self.public_key:
                manager.remove_peer_from_server(self)
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Помилка видалення WireGuard peer для пристрою {self.name}: {str(e)}")
        
        # Видаляємо модель
        super().delete(*args, **kwargs)


class ACLRule(models.Model):
    """Правило доступу (ACL)"""
    ACTION_CHOICES = [
        ('allow', 'Дозволити'),
        ('deny', 'Заборонити'),
    ]

    PROTOCOL_CHOICES = [
        ('tcp', 'TCP'),
        ('udp', 'UDP'),
        ('icmp', 'ICMP'),
        ('any', 'Будь-який'),
    ]

    name = models.CharField(
        max_length=100,
        verbose_name="Назва правила"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Опис"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='acl_rules',
        verbose_name="Локація"
    )
    source_group = models.ForeignKey(
        DeviceGroup,
        on_delete=models.CASCADE,
        related_name='source_rules',
        verbose_name="Група джерела",
        null=True,
        blank=True
    )
    source_ip = models.CharField(
        max_length=18,
        blank=True,
        verbose_name="IP джерела",
        help_text="IP або підмережа (наприклад: 10.0.0.0/24, any)"
    )
    destination_ip = models.CharField(
        max_length=18,
        verbose_name="IP призначення",
        help_text="IP або підмережа (наприклад: 10.0.0.0/24, any)"
    )
    protocol = models.CharField(
        max_length=4,
        choices=PROTOCOL_CHOICES,
        default='any',
        verbose_name="Протокол"
    )
    destination_port = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Порт призначення",
        help_text="Порт або діапазон (наприклад: 80, 80-90, any)"
    )
    action = models.CharField(
        max_length=5,
        choices=ACTION_CHOICES,
        verbose_name="Дія"
    )
    priority = models.PositiveIntegerField(
        default=100,
        verbose_name="Пріоритет",
        help_text="Чим менше число, тим вищий пріоритет"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активне"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Створено"
    )

    class Meta:
        verbose_name = "Правило ACL"
        verbose_name_plural = "Правила ACL"
        ordering = ['priority', 'name']

    def __str__(self):
        return f"{self.name} ({self.action})"


class UserLocationAccess(models.Model):
    """Доступ користувача до локації"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='location_access',
        verbose_name="Користувач"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='user_access',
        verbose_name="Локація"
    )
    is_admin = models.BooleanField(
        default=False,
        verbose_name="Адміністратор локації",
        help_text="Чи може користувач управляти цією локацією"
    )
    max_devices = models.PositiveIntegerField(
        default=5,
        verbose_name="Максимум пристроїв",
        help_text="Максимальна кількість пристроїв у цій локації"
    )
    granted_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Надано доступ"
    )
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='granted_access',
        verbose_name="Надав доступ"
    )

    class Meta:
        verbose_name = "Доступ до локації"
        verbose_name_plural = "Доступи до локацій"
        unique_together = [['user', 'location']]

    def __str__(self):
        return f"{self.user.username} -> {self.location.name}"
