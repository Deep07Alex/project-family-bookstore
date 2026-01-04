from django.shortcuts import render, get_object_or_404
from django.http import Http404
from .models import Book
from django.core.paginator import Paginator
from django.http import JsonResponse

def home_page(request):
    context = {
        'new_arrivals_books': Book.objects.filter(category='new_arrivals').order_by('title'),
        'manga_comics_books': Book.objects.filter(category='manga_comics').order_by('title'),
        'most_read_combos_books': Book.objects.filter(category='most_read_combos').order_by('title'),
        'self_improvements_books': Book.objects.filter(category='self_improvements', on_sale=True).order_by('title'),
        'romance_sale_books': Book.objects.filter(category='romance', on_sale=True).order_by('title'),
        'hindi_books': Book.objects.filter(category='hindi').order_by('title'),
        'business_stock_market_books': Book.objects.filter(category='business_stock_market').order_by('title'),
        'best_sellers_books': Book.objects.filter(category='best_sellers').order_by('title'),
    }
    return render(request, 'index.html', context)

def book_detail(request, slug):
    book = get_object_or_404(Book, slug=slug)
    suggested_books = Book.objects.exclude(id=book.id).order_by('?')[:10]
    return render(request, 'book_detail.html', {
        'book': book,
        'suggested_books': suggested_books,
        'model_type': 'book',
    })

CATEGORY_SLUG_MAP = {
    'new-arrivals': {'category': 'new_arrivals', 'on_sale': False, 'name': 'NEW ARRIVALS'},
    'manga-comics': {'category': 'manga_comics', 'on_sale': False, 'name': 'MANGA & COMICS'},
    'most-read-combos': {'category': 'most_read_combos', 'on_sale': False, 'name': 'MOST READ COMBOS'},
    'self-improvements': {'category': 'self_improvements', 'on_sale': True, 'name': 'SELF IMPROVEMENTS'},
    'romance-sale': {'category': 'romance', 'on_sale': True, 'name': 'ROMANCE ON SALE'},
    'hindi-books': {'category': 'hindi', 'on_sale': False, 'name': 'HINDI BOOKS'},
    'business-stock-market': {'category': 'business_stock_market', 'on_sale': False, 'name': 'BUSINESS & STOCK-MARKET'},
    'best-sellers': {'category': 'best_sellers', 'on_sale': False, 'name': 'BEST SELLERS'},
}

# homepage/views.py

def category_view(request, category_slug):
    config = CATEGORY_SLUG_MAP.get(category_slug)
    if not config:
        raise Http404(f"Category '{category_slug}' not found")

    books = Book.objects.filter(category=config['category'])
    if config['on_sale']:
        books = books.filter(on_sale=True)
    
    books = books.order_by('title')
    total_books = books.count()


    paginator = Paginator(books, 20) 
    books_page = paginator.page(1)

    has_more = books_page.has_next()
    
    return render(request, 'pages/category_detail.html', {
        'books': books_page.object_list,
        'category_name': config['name'],
        'category_slug': category_slug,
        'has_more': has_more,
        'total_books': total_books,
    })
    
def category_load_more(request, category_slug):
    config = CATEGORY_SLUG_MAP.get(category_slug)
    if not config:
        return JsonResponse({'success': False, 'error': 'Category not found'})
    
    try:
        page = int(request.GET.get('page', 2))
    except:
        page = 2
    
    books = Book.objects.filter(category=config['category'])
    if config['on_sale']:
        books = books.filter(on_sale=True)
    
    books = books.order_by('title')
    paginator = Paginator(books, 20)  # Must match initial load
    
    try:
        books_page = paginator.page(page)
    except:
        return JsonResponse({'success': False, 'error': 'No more books'})
    
    books_data = []
    for book in books_page:
        image_url = book.image.url if book.image else '/static/images/placeholder.png'
        
        books_data.append({
            'id': book.id,
            'title': book.title,
            'slug': book.slug,
            'price': str(book.price),
            'old_price': str(book.old_price) if book.old_price else None,
            'image_url': image_url,
            'on_sale': book.on_sale,
        })
    
    return JsonResponse({
        'success': True,
        'books': books_data,
        'has_next': books_page.has_next(),
    })
