from django.shortcuts import render ,get_object_or_404
from django.http import Http404
from .models import product_variety, Product
from homepage.models import Book
from django.core.paginator import Paginator
from django.http import JsonResponse

# Map type codes to models and display names
PRODUCT_CATEGORY_MAP = {
    'NEW': {'name': 'NEW ARRIVAL', 'model': Product, 'template': 'default'},
    'MNG': {'name': 'MANGA & COMICS', 'model': Product, 'template': 'comic'},
    'MRC': {'name': 'MOST READ COMBOS', 'model': Product, 'template': 'default'},
    'SFI': {'name': 'SELF IMPROVEMENTS', 'model': Product, 'template': 'default'},
    'ROS': {'name': 'ROMANCE ON SALE', 'model': Product, 'template': 'default'},
    'HIN': {'name': 'HINDI BOOKS', 'model': Product, 'template': 'default'},
    'BSM': {'name': 'BUSINESS & STOCK-MARKET', 'model': Product, 'template': 'default'},
    'BST': {'name': 'BEST SELLERS', 'model': Product, 'template': 'default'},  
}

def productcatagory(request):
    products = product_variety.objects.all().order_by('type')
    return render(request, 'pages/productcatagory.html', {'products_category': products})

def product_category_detail(request, category_type):
    """Show products for a specific category with pagination"""
    category_type = category_type.upper()
    category = get_object_or_404(product_variety, type=category_type)
    
    products = Product.objects.filter(category_id=category.id).order_by('title')
    total_products = products.count()
    
    # Paginate - show 20 initially
    paginator = Paginator(products, 20)
    products_page = paginator.page(1)
    
    has_more = products_page.has_next()
    
    return render(request, 'pages/product_category_detail.html', {
        'items': products_page.object_list,
        'category_name': category.get_type_display(),
        'category_type': category_type,
        'has_more': has_more,
        'total_products': total_products,
    })

def product_category_load_more(request, category_type):
    """AJAX endpoint to load more products"""
    category_type = category_type.upper()
    category = get_object_or_404(product_variety, type=category_type)
    
    try:
        page = int(request.GET.get('page', 2))
    except:
        page = 2
    
    products = Product.objects.filter(category_id=category.id).order_by('title')
    paginator = Paginator(products, 20)
    
    try:
        products_page = paginator.page(page)
    except:
        return JsonResponse({'success': False, 'error': 'No more products'})
    
    products_data = []
    for product in products_page:
        image_url = product.image.url if product.image else '/static/images/placeholder.png'
        
        products_data.append({
            'id': product.id,
            'title': product.title,
            'slug': product.slug,
            'price': str(product.price),
            'old_price': str(product.old_price) if product.old_price else None,
            'image_url': image_url,
            'on_sale': product.on_sale,
        })
    
    return JsonResponse({
        'success': True,
        'products': products_data, 
        'has_next': products_page.has_next(),  
    })
    
def product_detail(request, slug):
    """Display detailed view of a single book"""
    book = get_object_or_404(Product, slug=slug)
    
    # Get 10 related books from same category
    suggested_books = Book.objects.order_by('?')[:10]

    return render(request, 'book_detail.html', {
        'book': book,
        'suggested_books': suggested_books,
        'model_type': 'book',
    })