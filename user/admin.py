from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('shiprocket_sku',)  # Show SKU but prevent editing
    fields = ('title', 'item_type', 'item_id', 'shiprocket_sku', 'price', 'quantity', 'image_url')
    can_delete = False  # Prevent accidental deletion in inline view


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # All Shiprocket fields added to list view
    list_display = (
        "id",
        "full_name",
        "email",
        "phone_number",
        "status",
        "shiprocket_order_id",  # Shiprocket's order ID
        "shiprocket_status",     # Current status from webhook
        "awb_number",            # Tracking number
        "courier_name",          # Courier company
        "total",
        "created_at",
    )

    # Enhanced filters including Shiprocket status
    list_filter = (
        "status",
        "shiprocket_status",  # Filter by Shiprocket status
        "payment_method",
        "created_at",
    )
    
    # Search across all Shiprocket fields
    search_fields = (
        "full_name",
        "email",
        "phone_number",
        "id",
        "shiprocket_order_id",  # Search by Shiprocket ID
        "awb_number",           # Search by tracking number
    )
    
    #  Shiprocket fields are read-only (set by webhook)
    readonly_fields = (
        'tracking_data',
        'created_at',
        'updated_at',
        'shiprocket_order_id',
        'shiprocket_status',
        'awb_number',
        'courier_name',
        'label_url',
    )
    
    inlines = [OrderItemInline]
    
    # Organized into logical fieldsets
    fieldsets = (
        ("Customer Information", {
            "fields": (
                "full_name",
                "email",
                "verified_email",
                "phone_number",
            )
        }),
        ("Shipping Address", {
            "fields": (
                "address",
                "city",
                "state",
                "pin_code",
                "delivery_type",
            )
        }),
        ("Payment & Pricing", {
            "fields": (
                "payment_method",
                "payment_id",
                "subtotal",
                "shipping",
                "discount",
                "total",
            )
        }),
        ("Order Status", {
            "fields": ("status",)
        }),
        ("Shiprocket Tracking", {  # Dedicated Shiprocket section
            "fields": (
                "shiprocket_order_id",
                "shiprocket_status",
                "awb_number",
                "courier_name",
                "label_url",
            ),
            "classes": ("collapse",)  # Collapsible section
        }),
        ("System Metadata", {
            "fields": (
                "tracking_data",
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",)  # Collapsible section
        }),
    )

    def get_queryset(self, request):
        # Optimize queries with prefetch_related
        return super().get_queryset(request).prefetch_related('items')


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    #  Added shiprocket_sku to list display
    list_display = (
        "id",
        "order",
        "title",
        "item_type",
        "item_id",
        "shiprocket_sku",  #  Shiprocket SKU
        "price",
        "quantity",
    )
    
    list_filter = (
        "item_type",
        ("order__created_at", admin.DateFieldListFilter),  # Date filter
    )
    
    # Search by Shiprocket SKU
    search_fields = (
        "title",
        "order__id",
        "shiprocket_sku",  # Search by SKU
        "item_id",
    )
    
    readonly_fields = ("shiprocket_sku",)  # SKU is read-only
    list_select_related = ("order",)  # Optimize queries

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('order')