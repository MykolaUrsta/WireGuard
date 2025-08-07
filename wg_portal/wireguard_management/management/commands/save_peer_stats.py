from django.core.management.base import BaseCommand
from wg_portal.wireguard_management.models import WireGuardPeer, PeerMonitoring
from django.utils import timezone

class Command(BaseCommand):
    help = 'Зберігає поточну статистику трафіку peer\'ів для моніторингу'

    def handle(self, *args, **options):
        now = timezone.now()
        count = 0
        for peer in WireGuardPeer.objects.all():
            PeerMonitoring.objects.create(
                peer=peer,
                bytes_sent=peer.bytes_sent,
                bytes_received=peer.bytes_received,
                timestamp=now
            )
            count += 1
        self.stdout.write(self.style.SUCCESS(f'Збережено статистику для {count} peer\'ів'))
