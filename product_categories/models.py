# product_categories/models.py
from django.db import models
from django.utils import timezone
from django.urls import reverse
from django.utils.text import slugify
import re

class product_variety(models.Model):
    PRODUCT_TYPE_CHOICE = [
        ('NEW', 'NEW ARRIVAL'),
        ('MNG', 'MANGA & COMICS'),
        ('MRC', 'MOST READ COMBOS'),
        ('SFI', 'SELF IMPROVEMENTS'),
        ('ROS', 'ROMANCE ON SALE'),
        ('HIN', 'HINDI BOOKS'),
        ('BSM', 'BUSINESS & STOCK-MARKET'),
        ('BST', 'BEST SELLERS'),
    ]
    
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='product_categories')
    date_added = models.DateTimeField(default=timezone.now)
    type = models.CharField(max_length=4, choices=PRODUCT_TYPE_CHOICE, unique=True)
    
    def __str__(self):  
        return self.get_type_display()

class Product(models.Model):
    category = models.ForeignKey(product_variety, on_delete=models.CASCADE, related_name='products')
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    old_price = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    on_sale = models.BooleanField(default=False)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    date_added = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True, help_text="Description of the product")

    def save(self, *args, **kwargs):
        if not self.slug:
            clean_title = re.sub(r'[^\w\s-]', '', self.title)
            clean_title = re.sub(r'\s+', ' ', clean_title).strip()
            base_slug = slugify(clean_title)
            
            slug = base_slug
            counter = 1
            while self.__class__.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
                
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('book_detail', kwargs={'slug': self.slug})

    @property
    def image_url(self):
        """Return image URL for JavaScript"""
        if self.image:
            return self.image.url
        return '/static/images/placeholder.png'

    def __str__(self):  
        return f"{self.title} ({self.category.get_type_display()})"