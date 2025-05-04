# Generated manually

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ecommerce', '0003_reservationpayment_includes_menu_items_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='reservation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orders', to='ecommerce.reservation'),
        ),
    ]
