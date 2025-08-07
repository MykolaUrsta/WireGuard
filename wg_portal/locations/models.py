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
        verbose_name="Останнє підключення"
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
        """Чи пристрій онлайн (на основі останнього handshake)"""
        if not self.last_handshake:
            return False
        from django.utils import timezone
        return (timezone.now() - self.last_handshake).seconds < 300  # 5 хвилин

    @property
    def traffic_total(self):
        """Загальний трафік"""
        return self.bytes_sent + self.bytes_received


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
