from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_order_pending_review_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="delivery_method",
            field=models.CharField(
                choices=[("nova_poshta", "Nova Poshta"), ("pickup", "Pickup")],
                default="nova_poshta",
                max_length=20,
            ),
        ),
    ]
