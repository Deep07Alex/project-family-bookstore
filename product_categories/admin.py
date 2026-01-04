from django.contrib import admin
from .models import product_variety, Product

@admin.register(product_variety)
class ProductVarietyAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'date_added')
    list_filter = ('type',)
    search_fields = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'price', 'old_price', 'on_sale', 'date_added')
    list_filter = ('category', 'on_sale')
    search_fields = ('title',)
    ordering = ('-date_added',)

    fieldsets = (
        ('Product Details', {
            'fields': ('title', 'slug', 'category', 'image', 'description')
        }),
        ('Pricing', {
            'fields': ('price', 'old_price', 'on_sale')
        }),
        ('Date Information', {
            'fields': ('date_added',),
        }),
    )

    readonly_fields = ('date_added',)
