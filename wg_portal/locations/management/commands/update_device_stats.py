# locations/management/commands/update_device_stats.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from locations.models import Device, Location
import subprocess
import re


class Command(BaseCommand):
    help = 'Оновлює статистики пристроїв з WireGuard серверів'

    def handle(self, *args, **options):
        """Оновлює статистики всіх активних пристроїв"""
        self.stdout.write("Оновлення статистик пристроїв...")
        
        # Отримуємо всі активні локації
        active_locations = Location.objects.filter(is_active=True)
        
        for location in active_locations:
            self.update_location_stats(location)
            
        self.stdout.write(
            self.style.SUCCESS('Статистики успішно оновлені')
        )

    def update_location_stats(self, location):
        """Оновлює статистики для конкретної локації"""
        try:
            # Виконуємо команду wg show для отримання статистик
            # Використовуємо os.system для виконання команди в контейнері
            import os
            import tempfile
            
            # Створюємо тимчасовий файл для результату
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
                temp_filename = temp_file.name
            
            # Виконуємо команду через os.system
            cmd = f"wg show {location.interface_name} dump > {temp_filename} 2>/dev/null || echo 'no_data' > {temp_filename}"
            os.system(cmd)
            
            # Читаємо результат
            with open(temp_filename, 'r') as f:
                output = f.read().strip()
            
            # Видаляємо тимчасовий файл
            os.unlink(temp_filename)
            
            if output == 'no_data' or not output:
                self.stdout.write(f"Немає даних для {location.interface_name}")
                return
                
            # Парсимо вивід
            lines = output.split('\n')
            
            for line in lines[1:]:  # Пропускаємо заголовок
                if not line.strip():
                    continue
                    
                parts = line.split('\t')
                if len(parts) >= 6:
                    public_key = parts[0]
                    endpoint = parts[2] if parts[2] != '(none)' else None
                    bytes_received = int(parts[4]) if parts[4] != '0' else 0
                    bytes_sent = int(parts[5]) if parts[5] != '0' else 0
                    last_handshake_timestamp = int(parts[3]) if parts[3] != '0' else None
                    
                    # Знаходимо пристрій за публічним ключем
                    try:
                        device = Device.objects.get(
                            public_key=public_key,
                            location=location
                        )
                        
                        # Оновлюємо трафік
                        old_total = device.traffic_total
                        # Передаємо bytes_sent, bytes_received, last_handshake
                        device.update_traffic(bytes_sent, bytes_received, handshake_time=timezone.datetime.fromtimestamp(last_handshake_timestamp, tz=timezone.get_current_timezone()) if last_handshake_timestamp else None)
                        
                        # Оновлюємо last_handshake якщо є timestamp
                        if last_handshake_timestamp:
                            device.last_handshake = timezone.datetime.fromtimestamp(
                                last_handshake_timestamp, 
                                tz=timezone.get_current_timezone()
                            )
                        
                        # Якщо трафік змінився або є активне підключення
                        if device.traffic_total != old_total or endpoint:
                            if not device.connected_at:
                                device.connected_at = timezone.now()
                        
                        device.save()
                        
                        self.stdout.write(f"Оновлено {device.name}: {bytes_received}↓ {bytes_sent}↑")
                        
                    except Device.DoesNotExist:
                        self.stdout.write(f"Пристрій з ключем {public_key[:10]}... не знайдено")
                        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Неочікувана помилка для {location.name}: {e}')
            )

    def get_wg_stats_from_container(self, interface_name):
        """Альтернативний метод отримання статистик через docker exec"""
        try:
            # Виконуємо команду всередині WireGuard контейнера
            result = subprocess.run([
                'docker', 'compose', 'exec', '-T', 'vpn',
                'sh', '-c', f'wg show {interface_name}'
            ], capture_output=True, text=True, check=True)
            
            return result.stdout
            
        except subprocess.CalledProcessError:
            return None
