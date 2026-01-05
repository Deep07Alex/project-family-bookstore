from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('user', '0001_initial'),  # or whatever your last migration is
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='shiprocket_shipment_created',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='order',
            name='customer_notified',
            field=models.BooleanField(default=False, db_index=True),
        ),
    ]