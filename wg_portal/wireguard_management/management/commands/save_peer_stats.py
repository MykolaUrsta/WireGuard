from django.core.management.base import BaseCommand
from locations.models import Device
from wireguard_management.models import PeerMonitoring
from django.utils import timezone

class Command(BaseCommand):
    help = 'Зберігає поточну статистику трафіку пристроїв для моніторингу'

    def handle(self, *args, **options):
        from wireguard_management.models import WireGuardPeer
        import logging
        now = timezone.now()
        count = 0
        skipped = 0
        for device in Device.objects.filter(status='active'):
            # Пошук відповідного peer (WireGuardPeer) для пристрою
            peer = WireGuardPeer.objects.filter(user=device.user, ip_address=device.ip_address).first()
            if peer:
                PeerMonitoring.objects.create(
                    peer=peer,
                    bytes_sent=device.bytes_sent,
                    bytes_received=device.bytes_received,
                    timestamp=now
                )
                count += 1
            else:
                skipped += 1
                logging.warning(f"[save_peer_stats] Не знайдено WireGuardPeer для Device id={device.id}, user={device.user}, ip={device.ip_address}")
        self.stdout.write(self.style.SUCCESS(f'Збережено статистику для {count} пристроїв, пропущено {skipped}'))
