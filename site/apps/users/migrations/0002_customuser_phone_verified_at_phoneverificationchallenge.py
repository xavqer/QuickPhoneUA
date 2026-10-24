from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="phone_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="PhoneVerificationChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("purpose", models.CharField(choices=[("registration", "Реєстрація"), ("login", "Вхід"), ("password_reset", "Скидання пароля"), ("phone_change", "Зміна номера")], max_length=32)),
                ("phone", models.CharField(max_length=20)),
                ("code_hash", models.CharField(max_length=128)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("attempts_count", models.PositiveSmallIntegerField(default=0)),
                ("max_attempts", models.PositiveSmallIntegerField(default=5)),
                ("sent_message_id", models.CharField(blank=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="phone_verification_challenges",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="phoneverificationchallenge",
            index=models.Index(fields=["purpose", "phone", "created_at"], name="users_phonev_purpose_32accf_idx"),
        ),
        migrations.AddIndex(
            model_name="phoneverificationchallenge",
            index=models.Index(fields=["user", "purpose", "created_at"], name="users_phonev_user_id_03bff3_idx"),
        ),
    ]
