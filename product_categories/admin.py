from django.contrib import admin
from .models import product_variety


@admin.register(product_variety)
class ProductVarietyAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'date_added')
    list_filter = ('type',)
    search_fields = ('name',)