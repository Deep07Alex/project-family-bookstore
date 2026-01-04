from django.contrib import admin
from .models import Book

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'price', 'old_price', 'on_sale', 'date_added')
    list_filter = ('category', 'on_sale', 'date_added') 
    search_fields = ('title',)
    ordering = ('-date_added',)

    fieldsets = (
        ('Book Details', {
            'fields': ('title', 'slug', 'image', 'category', 'description')  
        }),
        ('Pricing', {
            'fields': ('price', 'old_price', 'on_sale')
        }),
        ('Date Information', {
            'fields': ('date_added',),
        }),
    )

    readonly_fields = ('date_added',)
