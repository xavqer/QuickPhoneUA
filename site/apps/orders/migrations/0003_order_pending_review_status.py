from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending_review", "Pending review"),
                    ("confirmed", "Confirmed"),
                    ("shipped", "Shipped"),
                    ("delivered", "Delivered"),
                    ("cancelled", "Cancelled"),
                ],
                default="pending_review",
                max_length=20,
            ),
        ),
    ]
