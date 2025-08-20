from django.db.models.signals import post_delete
from django.dispatch import receiver
from wireguard_management.models import WireGuardPeer
from locations.models import Device

@receiver(post_delete, sender=WireGuardPeer)
def delete_device_on_peer_delete(sender, instance, **kwargs):
    # Видаляємо Device з таким же user та ip_address
    Device.objects.filter(user=instance.user, ip_address=instance.ip_address).delete()
