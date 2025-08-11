from django.core.management.base import BaseCommand
from wireguard_management.models import WireGuardPeer
from django.utils import timezone
import subprocess
import json
import re

class Command(BaseCommand):
    help = 'Оновлює статус та статистику peer\'ів з WireGuard'

    def handle(self, *args, **options):
        self.stdout.write('Оновлення статистики peer\'ів...')
        
        try:
            # Отримуємо статистику з wg show
            result = subprocess.run(['wg', 'show', 'all', 'dump'], 
                                    capture_output=True, text=True)
            
            if result.returncode != 0:
                self.stdout.write(self.style.ERROR('Не вдалося отримати статистику WireGuard'))
                return
            
            # Парсимо вивід
            lines = result.stdout.strip().split('\n')
            peer_stats = {}
            
            for line in lines:
                if not line:
                    continue
                    
                parts = line.split('\t')
                if len(parts) >= 6:
                    interface = parts[0]
                    public_key = parts[1]
                    endpoint = parts[2] if parts[2] != '(none)' else None
                    allowed_ips = parts[3]
                    latest_handshake = int(parts[4]) if parts[4] != '0' else None
                    rx_bytes = int(parts[5]) if parts[5] else 0
                    tx_bytes = int(parts[6]) if len(parts) > 6 and parts[6] else 0
                    
                    peer_stats[public_key] = {
                        'interface': interface,
                        'endpoint': endpoint,
                        'latest_handshake': latest_handshake,
                        'rx_bytes': rx_bytes,
                        'tx_bytes': tx_bytes,
                        'is_online': latest_handshake is not None and 
                                   (timezone.now().timestamp() - latest_handshake) < 180
                    }
            
            # Оновлюємо peer'ів в базі даних
            updated_count = 0
            for peer in WireGuardPeer.objects.all():
                if peer.public_key in peer_stats:
                    stats = peer_stats[peer.public_key]
                    
                    # Оновлюємо статистику
                    peer.bytes_sent = stats['tx_bytes']
                    peer.bytes_received = stats['rx_bytes']
                    
                    # Оновлюємо час останнього handshake
                    if stats['latest_handshake']:
                        new_handshake = timezone.datetime.fromtimestamp(
                            stats['latest_handshake'], tz=timezone.utc
                        )
                        
                        # Якщо це новий handshake і peer раніше не був підключений
                        if (not peer.last_handshake or 
                            new_handshake > peer.last_handshake):
                            
                            # Якщо peer не був онлайн, встановлюємо час підключення
                            if (not peer.connected_at or 
                                not peer.last_handshake or 
                                (peer.last_handshake and 
                                 (timezone.now() - peer.last_handshake).total_seconds() > 180)):
                                peer.connected_at = new_handshake
                        
                        peer.last_handshake = new_handshake
                    
                    # Оновлюємо статус онлайн
                    peer.is_online = stats['is_online']
                    
                    # Якщо peer офлайн, очищуємо connected_at
                    if not stats['is_online']:
                        peer.connected_at = None
                    
                    peer.save(update_fields=[
                        'bytes_sent', 'bytes_received', 'last_handshake', 
                        'is_online', 'connected_at'
                    ])
                    updated_count += 1
                else:
                    # Peer не знайдений в WireGuard - позначаємо як офлайн
                    if peer.is_online:
                        peer.is_online = False
                        peer.connected_at = None
                        peer.save(update_fields=['is_online', 'connected_at'])
                        updated_count += 1
            
            self.stdout.write(
                self.style.SUCCESS(f'Оновлено {updated_count} peer\'ів')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Помилка при оновленні статистики: {e}')
            )
