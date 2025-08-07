from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ("wireguard_management", "0001_initial")
    ]

    operations = [
        migrations.CreateModel(
            name="PeerMonitoring",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                ("bytes_sent", models.BigIntegerField(default=0)),
                ("bytes_received", models.BigIntegerField(default=0)),
                ("peer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="monitoring", to="wireguard_management.WireGuardPeer")),
            ],
            options={
                "verbose_name": "Моніторинг peer'а",
                "verbose_name_plural": "Моніторинг peer'ів",
                "ordering": ["-timestamp"],
            },
        ),
    ]
