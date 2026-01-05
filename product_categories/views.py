from django.shortcuts import render ,get_object_or_404
from django.http import Http404
from .models import product_variety, Product
from homepage.models import Book
from django.core.paginator import Paginator
from django.http import JsonResponse

# Map type codes to models and display names
CATEGORY_TYPE_TO_SLUG = {
    'NEW': 'new-arrivals',
    'MNG': 'manga-comics',
    'MRC': 'most-read-combos',
    'SFI': 'self-improvements',
    'ROS': 'romance-sale',
    'HIN': 'hindi-books',
    'BSM': 'business-stock-market',
    'BST': 'best-sellers',
}


def productcatagory(request):
    """Show all product categories and map them to the unified category pages"""
    products = product_variety.objects.all().order_by('type')
    
    # Add slug mapping for each category
    categories_with_slugs = []
    for category in products:
        categories_with_slugs.append({
            'category': category,
            'slug': CATEGORY_TYPE_TO_SLUG.get(category.type, '')
        })
    
    return render(request, 'pages/productcatagory.html', {
        'categories_with_slugs': categories_with_slugs,
    })
def product_detail(request, slug):
    """Display detailed view of a single product"""
    book = get_object_or_404(Product, slug=slug)
    suggested_books = Book.objects.order_by('?')[:10]
    return render(request, 'book_detail.html', {
        'book': book,
        'suggested_books': suggested_books,
        'model_type': 'book',
    })