from django import forms
from .models import Location, Network, AccessControlList, Device, DeviceGroup
from django.core.exceptions import ValidationError
import ipaddress
import subprocess
import logging

logger = logging.getLogger(__name__)


class LocationForm(forms.ModelForm):
    # Додаткові поля для налаштування WireGuard мережі
    create_network = forms.BooleanField(
        required=False,
        initial=True,
        label="Створити мережу WireGuard",
        help_text="Автоматично створити та налаштувати мережу WireGuard для цієї локації"
    )
    network_name = forms.CharField(
        max_length=100,
        required=False,
        label="Назва мережі",
        help_text="Назва мережі WireGuard (за замовчуванням буде використана назва локації)"
    )
    network_subnet = forms.CharField(
        max_length=18,
        required=False,
        initial="10.0.0.0/24",
        label="Підмережа",
        help_text="CIDR підмережа для WireGuard (наприклад: 10.0.0.0/24)"
    )
    interface_name = forms.CharField(
        max_length=15,
        required=False,
        initial="wg0",
        label="Інтерфейс WireGuard",
        help_text="Назва WireGuard інтерфейсу (наприклад: wg0, wg1)"
    )
    dns_servers = forms.CharField(
        max_length=255,
        required=False,
        initial="8.8.8.8,8.8.4.4",
        label="DNS сервери",
        help_text="DNS сервери через кому (наприклад: 8.8.8.8,8.8.4.4)"
    )
    apply_to_wireguard = forms.BooleanField(
        required=False,
        initial=True,
        label="Застосувати до WireGuard",
        help_text="Автоматично застосувати налаштування до WireGuard сервера"
    )

    class Meta:
        model = Location
        fields = ['name', 'description', 'server_ip', 'server_port', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Назва локації (наприклад: Київ, Львів)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Опис локації'
            }),
            'server_ip': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '192.168.1.1'
            }),
            'server_port': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 65535,
                'value': 51820
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Додаємо класи Bootstrap до нових полів
        self.fields['network_name'].widget.attrs.update({'class': 'form-control'})
        self.fields['network_subnet'].widget.attrs.update({'class': 'form-control'})
        self.fields['interface_name'].widget.attrs.update({'class': 'form-control'})
        self.fields['dns_servers'].widget.attrs.update({'class': 'form-control'})

    def clean_network_subnet(self):
        subnet = self.cleaned_data.get('network_subnet')
        create_network = self.cleaned_data.get('create_network')
        
        if create_network and subnet:
            try:
                network = ipaddress.IPv4Network(subnet, strict=False)
                return str(network)
            except ipaddress.AddressValueError:
                raise ValidationError("Введіть правильну підмережу у форматі CIDR")
        return subnet

    def clean_interface_name(self):
        interface = self.cleaned_data.get('interface_name')
        create_network = self.cleaned_data.get('create_network')
        
        if create_network and interface:
            if not interface.startswith('wg'):
                raise ValidationError("Назва інтерфейсу повинна починатися з 'wg'")
        return interface

    def save(self, commit=True):
        location = super().save(commit=commit)
        
        # Якщо потрібно створити мережу
        if self.cleaned_data.get('create_network') and commit:
            self._create_wireguard_network(location)
            
        return location

    def _create_wireguard_network(self, location):
        """Створення мережі WireGuard для локації"""
        try:
            from .models import Network
            
            network_name = self.cleaned_data.get('network_name') or f"{location.name} Network"
            subnet = self.cleaned_data.get('network_subnet', "10.0.0.0/24")
            interface = self.cleaned_data.get('interface_name', "wg0")
            dns_servers = self.cleaned_data.get('dns_servers', "8.8.8.8,8.8.4.4")
            apply_to_wg = self.cleaned_data.get('apply_to_wireguard', True)
            
            # Створюємо мережу в базі даних
            network = Network.objects.create(
                location=location,
                name=network_name,
                subnet=subnet,
                interface=interface,
                server_port=location.server_port,
                dns_servers=dns_servers,
                is_active=True
            )
            
            # Застосовуємо до WireGuard сервера
            if apply_to_wg:
                self._apply_to_wireguard_server(network)
                
            logger.info(f"Створено мережу WireGuard: {network_name} для локації {location.name}")
            
        except Exception as e:
            logger.error(f"Помилка при створенні мережі WireGuard: {str(e)}")
            raise ValidationError(f"Не вдалося створити мережу WireGuard: {str(e)}")

    def _apply_to_wireguard_server(self, network):
        """Застосування налаштувань до WireGuard сервера"""
        try:
            # Генеруємо конфігурацію WireGuard
            config_content = self._generate_wg_config(network)
            
            # Записуємо конфігурацію у файл
            config_path = f"/etc/wireguard/{network.interface}.conf"
            
            # Створюємо команди для застосування
            commands = [
                f"wg-quick down {network.interface}",  # Зупиняємо інтерфейс (якщо існує)
                f"echo '{config_content}' > {config_path}",  # Записуємо конфігурацію
                f"wg-quick up {network.interface}",  # Запускаємо інтерфейс
                f"systemctl enable wg-quick@{network.interface}"  # Автозапуск
            ]
            
            for cmd in commands:
                try:
                    result = subprocess.run(
                        cmd, 
                        shell=True, 
                        capture_output=True, 
                        text=True,
                        timeout=30
                    )
                    if result.returncode != 0 and "does not exist" not in result.stderr:
                        logger.warning(f"Команда '{cmd}' повернула код {result.returncode}: {result.stderr}")
                except subprocess.TimeoutExpired:
                    logger.error(f"Timeout при виконанні команди: {cmd}")
                except Exception as e:
                    logger.error(f"Помилка при виконанні команди '{cmd}': {str(e)}")
                    
        except Exception as e:
            logger.error(f"Помилка при застосуванні налаштувань WireGuard: {str(e)}")
            # Не кидаємо помилку, щоб не блокувати створення локації

    def _generate_wg_config(self, network):
        """Генерація конфігурації WireGuard"""
        try:
            # Генеруємо приватний та публічний ключі сервера
            private_key = self._generate_private_key()
            public_key = self._generate_public_key(private_key)
            
            # Отримуємо IP сервера з підмережі
            server_ip = str(list(ipaddress.IPv4Network(network.subnet).hosts())[0])
            
            config = f"""[Interface]
PrivateKey = {private_key}
Address = {server_ip}/{network.subnet.split('/')[1]}
ListenPort = {network.server_port}
DNS = {network.dns_servers.replace(',', ', ')}

# PostUp та PostDown правила для маршрутизації
PostUp = iptables -A FORWARD -i {network.interface} -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i {network.interface} -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

# Клієнти будуть додані автоматично
"""
            return config
            
        except Exception as e:
            logger.error(f"Помилка при генерації конфігурації WireGuard: {str(e)}")
            return ""

    def _generate_private_key(self):
        """Генерація приватного ключа WireGuard"""
        try:
            result = subprocess.run(['wg', 'genkey'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.error(f"Помилка при генерації приватного ключа: {result.stderr}")
                return "GENERATED_PRIVATE_KEY_PLACEHOLDER"
        except Exception as e:
            logger.error(f"Помилка при генерації приватного ключа: {str(e)}")
            return "GENERATED_PRIVATE_KEY_PLACEHOLDER"

    def _generate_public_key(self, private_key):
        """Генерація публічного ключа з приватного"""
        try:
            result = subprocess.run(
                ['wg', 'pubkey'], 
                input=private_key, 
                capture_output=True, 
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.error(f"Помилка при генерації публічного ключа: {result.stderr}")
                return "GENERATED_PUBLIC_KEY_PLACEHOLDER"
        except Exception as e:
            logger.error(f"Помилка при генерації публічного ключа: {str(e)}")
            return "GENERATED_PUBLIC_KEY_PLACEHOLDER"


class NetworkForm(forms.ModelForm):
    class Meta:
        model = Network
        fields = [
            'location', 'name', 'subnet', 'interface', 
            'server_port', 'dns_servers', 'is_active'
        ]
        widgets = {
            'location': forms.Select(attrs={
                'class': 'form-control'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Назва мережі (наприклад: Main Network)'
            }),
            'subnet': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '10.13.13.0/24'
            }),
            'interface': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'wg0'
            }),
            'server_port': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 65535,
                'value': 51820
            }),
            'dns_servers': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '1.1.1.1,8.8.8.8'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    def clean(self):
        cleaned_data = super().clean()
        subnet = cleaned_data.get('subnet')

        if subnet:
            try:
                # Перевіряємо валідність підмережі
                network = ipaddress.IPv4Network(subnet, strict=False)
            except ipaddress.AddressValueError as e:
                raise ValidationError({
                    'subnet': 'Некоректний формат підмережі'
                })

        return cleaned_data


class AccessControlListForm(forms.ModelForm):
    class Meta:
        model = AccessControlList
        fields = [
            'name', 'description', 'network', 'source_groups', 'destination_groups',
            'protocol', 'port_ranges', 'action', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Назва ACL правила'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Опис правила'
            }),
            'network': forms.Select(attrs={
                'class': 'form-control'
            }),
            'source_groups': forms.SelectMultiple(attrs={
                'class': 'form-control',
                'size': 5
            }),
            'destination_groups': forms.SelectMultiple(attrs={
                'class': 'form-control',
                'size': 5
            }),
            'protocol': forms.Select(attrs={
                'class': 'form-control'
            }),
            'port_ranges': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '80,443,8000-9000'
            }),
            'action': forms.Select(attrs={
                'class': 'form-control'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }


class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ['location', 'network', 'group', 'name', 'description']
        widgets = {
            'location': forms.Select(attrs={
                'class': 'form-control'
            }),
            'network': forms.Select(attrs={
                'class': 'form-control'
            }),
            'group': forms.Select(attrs={
                'class': 'form-control'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Назва пристрою (наприклад: Laptop, Phone)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Опис пристрою'
            })
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Фільтруємо локації тільки активні
        self.fields['location'].queryset = Location.objects.filter(is_active=True)
        
        # Фільтруємо мережі тільки активні
        self.fields['network'].queryset = Network.objects.filter(is_active=True)
        
        # Додаємо пустий вибір для групи
        self.fields['group'].queryset = DeviceGroup.objects.all()
        self.fields['group'].required = False
        self.fields['network'].required = False

    def save(self, commit=True):
        device = super().save(commit=False)
        if self.user:
            device.user = self.user
        
        # Генеруємо ключі WireGuard якщо потрібно
        if not device.public_key or not device.private_key:
            from ..wireguard_management.utils import generate_keypair
            private_key, public_key = generate_keypair()
            device.private_key = private_key
            device.public_key = public_key
        
        # Присвоюємо наступну доступну IP адресу
        if not device.ip_address and device.location:
            # Тут потрібна логіка присвоєння IP адреси
            pass
        
        if commit:
            device.save()
            self.save_m2m()
        
        return device


class QuickNetworkForm(forms.Form):
    """Форма для швидкого створення локації та мережі"""
    location_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Назва локації (наприклад: Офіс Київ)'
        }),
        label='Назва локації'
    )
    
    endpoint = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'vpn.example.com або 192.168.1.1'
        }),
        label='Endpoint сервера'
    )
    
    port = forms.IntegerField(
        initial=51820,
        min_value=1,
        max_value=65535,
        widget=forms.NumberInput(attrs={
            'class': 'form-control'
        }),
        label='Порт WireGuard'
    )
    
    network_name = forms.CharField(
        max_length=100,
        initial='Main Network',
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        }),
        label='Назва мережі'
    )
    
    subnet = forms.CharField(
        initial='10.13.13.0/24',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '10.13.13.0/24'
        }),
        label='Підмережа'
    )
    
    server_ip = forms.CharField(
        initial='10.13.13.1',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '10.13.13.1'
        }),
        label='IP сервера'
    )

    def clean(self):
        cleaned_data = super().clean()
        subnet = cleaned_data.get('subnet')
        server_ip = cleaned_data.get('server_ip')

        if subnet and server_ip:
            try:
                network = ipaddress.IPv4Network(subnet, strict=False)
                server_ip_obj = ipaddress.IPv4Address(server_ip)
                
                if server_ip_obj not in network:
                    raise ValidationError({
                        'server_ip': f'IP сервера {server_ip} не належить до мережі {subnet}'
                    })
            except ipaddress.AddressValueError:
                raise ValidationError('Некоректний формат підмережі або IP адреси')

        return cleaned_data

    def save(self):
        """Створює локацію та мережу"""
        data = self.cleaned_data
        
        # Створюємо локацію
        location = Location.objects.create(
            name=data['location_name'],
            server_ip=data['endpoint'],
            server_port=data['port'],
            is_active=True
        )
        
        # Створюємо мережу
        network = Network.objects.create(
            location=location,
            name=data['network_name'],
            subnet=data['subnet'],
            interface='wg0',
            is_active=True
        )
        
        return location, network
