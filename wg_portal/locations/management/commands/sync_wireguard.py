"""
Django management команда для синхронізації WireGuard конфігурації
"""

from django.core.management.base import BaseCommand
from locations.models import Location
from locations.docker_manager import WireGuardDockerManager
import logging

class Command(BaseCommand):
    help = 'Синхронізує WireGuard конфігурацію з налаштуваннями локацій'

    def add_arguments(self, parser):
        parser.add_argument(
            '--location',
            type=str,
            help='ID або назва локації для синхронізації (по замовчуванню - всі активні)',
        )
        parser.add_argument(
            '--restart',
            action='store_true',
            help='Перезапустити WireGuard після синхронізації',
        )

    def handle(self, *args, **options):
        location_filter = options.get('location')
        restart = options.get('restart', False)
        
        manager = WireGuardDockerManager()
        
        # Визначаємо які локації синхронізувати
        if location_filter:
            try:
                # Спробуємо знайти по ID
                if location_filter.isdigit():
                    locations = Location.objects.filter(id=int(location_filter))
                else:
                    # Інакше по назві
                    locations = Location.objects.filter(name__icontains=location_filter)
            except (ValueError, Location.DoesNotExist):
                self.stdout.write(
                    self.style.ERROR(f'Локація "{location_filter}" не знайдена')
                )
                return
        else:
            # Синхронізуємо всі активні локації
            locations = Location.objects.filter(is_active=True)

        if not locations.exists():
            self.stdout.write(
                self.style.WARNING('Не знайдено локацій для синхронізації')
            )
            return

        success_count = 0
        for location in locations:
            self.stdout.write(f'Синхронізація локації: {location.name}')
            
            try:
                # Генеруємо конфігурацію сервера
                if manager.generate_server_config(location):
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Конфігурація для {location.name} оновлена')
                    )
                    success_count += 1
                else:
                    self.stdout.write(
                        self.style.ERROR(f'✗ Помилка оновлення конфігурації для {location.name}')
                    )
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Помилка обробки {location.name}: {str(e)}')
                )

        # Перезапускаємо WireGuard якщо потрібно
        if restart and success_count > 0:
            self.stdout.write('Перезапуск WireGuard...')
            if manager.restart_wireguard():
                self.stdout.write(
                    self.style.SUCCESS('✓ WireGuard перезапущено')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('✗ Помилка перезапуску WireGuard')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Синхронізація завершена. Оброблено: {success_count} локацій')
        )
