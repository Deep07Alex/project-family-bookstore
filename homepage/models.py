# homepage/models.py
from django.db import models
from django.utils import timezone
from django.urls import reverse
from django.utils.text import slugify
import re

class Book(models.Model):
    CATEGORY_CHOICES = [
        ('new_arrivals', 'New Arrivals'),
        ('manga_comics', 'Manga & Comics'),
        ('most_read_combos', 'Most Read Combos'),
        ('self_improvements', 'Self Improvements'),
        ('romance', 'Romance'),
        ('hindi', 'Hindi Books'),
        ('business_stock_market', 'Business & Stock Market'),
        ('best_sellers', 'Best Sellers'),
    ]
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    old_price = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    on_sale = models.BooleanField(default=False)
    image = models.ImageField(upload_to='books/', blank=True, null=True)
    date_added = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)

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
        return f"{self.title} ({self.get_category_display()})"