from django.core.management.base import BaseCommand
from locations.models import Device
from wireguard_management.models import PeerMonitoring
from django.utils import timezone

class Command(BaseCommand):
    help = 'Зберігає поточну статистику трафіку пристроїв для моніторингу'

    def handle(self, *args, **options):
        now = timezone.now()
        count = 0
        for device in Device.objects.filter(status='active'):
            PeerMonitoring.objects.create(
                peer_id=device.id,  # Використовуємо ID пристрою
                bytes_sent=device.bytes_sent,
                bytes_received=device.bytes_received,
                timestamp=now
            )
            count += 1
        self.stdout.write(self.style.SUCCESS(f'Збережено статистику для {count} пристроїв'))
