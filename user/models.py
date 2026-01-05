# user/models.py - PRODUCTION READY
from django.db import models

class Order(models.Model):
    STATUS_CHOICES = [
        ("pending_payment", "Pending Payment"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("cancelled", "Cancelled"),
    ]

    # Contact & Shipping
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    full_name = models.CharField(max_length=200)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pin_code = models.CharField(max_length=10)
    delivery_type = models.CharField(max_length=100, default="Standard (3-6 days)")

    # Payment
    payment_method = models.CharField(max_length=50, default="card")
    payment_id = models.CharField(max_length=100, blank=True, null=True, unique=True, db_index=True)
    payu_txnid = models.CharField(max_length=100, blank=True, null=True, unique=True, db_index=True)

    # Pricing
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending_payment", db_index=True)
    
    # Shiprocket Integration
    shiprocket_order_id = models.CharField(max_length=100, blank=True, null=True, unique=True, db_index=True)
    shiprocket_status = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    awb_number = models.CharField(max_length=100, blank=True, null=True, unique=True, db_index=True)
    courier_name = models.CharField(max_length=200, blank=True, null=True)
    label_url = models.URLField(blank=True, null=True)
    tracking_data = models.JSONField(default=dict, blank=True)
    
    # Idempotency Flags (CRITICAL: Prevents duplicate processing)
    shiprocket_shipment_created = models.BooleanField(default=False, db_index=True)
    customer_notified = models.BooleanField(default=False, db_index=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['shiprocket_order_id']),
            models.Index(fields=['payment_id']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['payment_id'], name='unique_payment_id', condition=~models.Q(payment_id="")),
            models.UniqueConstraint(fields=['shiprocket_order_id'], name='unique_shiprocket_order', condition=~models.Q(shiprocket_order_id="")),
            models.UniqueConstraint(fields=['payu_txnid'], name='unique_payu_txnid', condition=~models.Q(payu_txnid="")),
        ]

    def __str__(self):
        return f"Order #{self.id} - {self.full_name}"

class OrderItem(models.Model):
    ITEM_TYPE_CHOICES = [
        ("book", "Book"),
        ("addon", "Addon"),
    ]

    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES, default="book")
    item_id = models.IntegerField()
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    image_url = models.URLField(blank=True, null=True)
    shiprocket_sku = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.title} x {self.quantity}"