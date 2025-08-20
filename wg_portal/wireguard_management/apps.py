from django.apps import AppConfig

class WireguardManagementConfig(AppConfig):
    name = 'wireguard_management'

    def ready(self):
        from . import signals
