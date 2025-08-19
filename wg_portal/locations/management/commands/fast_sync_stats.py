# locations/management/commands/fast_sync_stats.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from locations.models import Location, Device
import subprocess
import datetime


class Command(BaseCommand):
    help = 'Швидко синхронізує статистики WireGuard'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interface',
            type=str,
            help='Інтерфейс для синхронізації (опціонально)',
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Тихий режим',
        )

    def handle(self, *args, **options):
        """Швидко оновлює статистики всіх активних пристроїв"""
        interface = options.get('interface')
        self.quiet = options.get('quiet', False)
        
        if interface:
            try:
                location = Location.objects.get(interface_name=interface, is_active=True)
                self.sync_location(location)
            except Location.DoesNotExist:
                if not self.quiet:
                    self.stdout.write(f"Локація з інтерфейсом {interface} не знайдена")
        else:
            # Оновлюємо всі активні локації
            active_locations = Location.objects.filter(is_active=True)
            for location in active_locations:
                self.sync_location(location)

    def sync_location(self, location):
        """Синхронізує статистики для однієї локації"""
        try:
            # Виконуємо команду в VPN контейнері
            result = subprocess.run([
                'docker', 'exec', 'wireguard_vpn',
                'wg', 'show', location.interface_name, 'dump'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                devices_data = self.parse_wg_output(result.stdout)
                
                # Оновлюємо статистики
                updated_count = 0
                for device in location.devices.all():
                    if device.public_key in devices_data:
                        data = devices_data[device.public_key]
                        if data['last_handshake']:
                            new_handshake = timezone.make_aware(
                                datetime.datetime.fromtimestamp(data['last_handshake'])
                            )
                            # Якщо пристрій був offline і став online — оновлюємо connected_at
                            if not device.is_online:
                                device.connected_at = new_handshake
                            device.last_handshake = new_handshake
                        device.bytes_received = data['bytes_received']
                        device.bytes_sent = data['bytes_sent']
                        device.endpoint = data['endpoint']
                        device.save()
                        updated_count += 1
                
                if not self.quiet:
                    self.stdout.write(f"Оновлено {updated_count} пристроїв для локації {location.name}")
            else:
                if not self.quiet:
                    self.stdout.write(f"Помилка отримання статистик для {location.name}: {result.stderr}")
        except Exception as e:
            if not self.quiet:
                self.stdout.write(f"Помилка синхронізації {location.name}: {str(e)}")

    def parse_wg_output(self, wg_output):
        """Парсить вивід команди wg show dump"""
        devices = {}
        lines = wg_output.strip().split('\n')
        
        # Перший рядок - це інтерфейс, пропускаємо
        # Наступні рядки - пірінги
        for line in lines[1:]:  # Пропускаємо заголовок інтерфейсу
            if not line.strip():
                continue
                
            parts = line.split('\t')
            if len(parts) >= 8:  # Формат: public_key, preshared_key, endpoint, allowed_ips, last_handshake, bytes_received, bytes_sent, persistent_keepalive
                public_key = parts[0]
                last_handshake = int(parts[4]) if parts[4] != '0' else None
                bytes_received = int(parts[5]) if parts[5] != '0' else 0
                bytes_sent = int(parts[6]) if parts[6] != '0' else 0
                
                devices[public_key] = {
                    'public_key': public_key,
                    'endpoint': parts[2] if parts[2] != '(none)' else None,
                    'last_handshake': last_handshake,
                    'bytes_received': bytes_received,
                    'bytes_sent': bytes_sent,
                }
        
        return devices
