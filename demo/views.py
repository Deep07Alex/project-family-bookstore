from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q

from homepage.models import Book
from product_categories.models import Product

import logging
from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
import json

logger = logging.getLogger(__name__)



def normalize_title(title):
    return title.lower().strip().replace(" ", "_")


def search_suggestions(request):
    """Return JSON search results for live autocomplete - no duplicates"""
    query = request.GET.get("q", "").strip()
    results = []
    seen_titles = set()

    if len(query) >= 2:
        # Search books from homepage
        books = Book.objects.filter(
            Q(title__icontains=query) | Q(category__icontains=query)
        )[:5]

        for book in books:
            title_lower = book.title.lower().strip()
            if title_lower not in seen_titles:
                seen_titles.add(title_lower)
                results.append(
                    {
                        "title": book.title,
                        "price": str(book.price),
                        "image": book.image.url if book.image else "",
                        "url": f"/books/{book.slug}/",
                        "type": "Book",
                    }
                )

        # Search products from product_categories
        products = Product.objects.filter(
            Q(title__icontains=query) | Q(category__name__icontains=query)
        )[:5]

        for product in products:
            title_lower = product.title.lower().strip()
            if title_lower not in seen_titles:
                seen_titles.add(title_lower)
                results.append(
                    {
                        "title": product.title,
                        "price": str(product.price),
                        "image": product.image.url if product.image else "",
                        "url": f"/product/{product.id}/",
                        "type": "Product",
                    }
                )

    return JsonResponse({"results": results})


def buy_now(request, book_id):
    """Add a single book to cart and redirect to checkout"""
    from user.views import save_cart  # import from user app to avoid duplicate helpers

    book = get_object_or_404(Book, id=book_id)

    cart = {}
    key = f"book_{book.id}"
    cart[key] = {
        "id": book.id,
        "type": "book",
        "title": book.title,
        "price": str(book.price),
        "image": book.image.url if book.image else "",
        "quantity": 1,
    }
    save_cart(request, cart)

    return redirect("checkout")


def search(request):
    """Handle search page requests"""
    query = request.GET.get("q", "").strip()
    results = []

    if query:
        book_results = Book.objects.filter(
            Q(title__icontains=query) | Q(category__icontains=query)
        )
        product_results = Product.objects.filter(
            Q(title__icontains=query) | Q(category__name__icontains=query)
        )
        results = list(book_results) + list(product_results)

    return render(
        request,
        "pages/search_results.html",
        {"query": query, "results": results},
    )


def home_page(request):
    return render(request, "index.html")


def Aboutus(request):
    return render(request, "pages/Aboutus.html")


def contact_information(request):
    return render(request, "pages/contactinformation.html")


@require_http_methods(["GET", "POST"])
def bulk_purchase(request):
    """Handle bulk purchase inquiry form"""
    if request.method == "POST":
        try:
            # Parse JSON or FormData
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            
            name = data.get('name', '').strip()
            email = data.get('email', '').strip()
            phone = data.get('phone', '').strip()
            comment = data.get('comment', '').strip()
            
            # Validation
            if not all([name, email, phone, comment]):
                return JsonResponse({
                    "success": False, 
                    "error": "All fields are required"
                }, status=400)
            
            if '@' not in email:
                return JsonResponse({
                    "success": False, 
                    "error": "Invalid email address"
                }, status=400)
            
            # Compose email
            subject = f'🛒 Bulk Purchase Inquiry from {name}'
            
            message = f"""
Hello Admin,

A new bulk purchase inquiry has been submitted!

═══════════════════════════════════════

👤 CUSTOMER DETAILS:
Name: {name}
Email: {email}
Phone: {phone}

📋 INQUIRY DETAILS:
{comment}

═══════════════════════════════════════

Please respond within 24 hours.

Family BookStore System
            """.strip()
            
            # Send to cs.familybookstore@gmail.com
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['cs.familybookstore@gmail.com'],
                fail_silently=False,
            )
            
            logger.info(f"Bulk inquiry sent from {email}")
            
            return JsonResponse({
                "success": True, 
                "message": "Your inquiry has been sent! We'll contact you within 24 hours."
            })
            
        except Exception as e:
            logger.error(f"Bulk purchase error: {str(e)}", exc_info=True)
            return JsonResponse({
                "success": False, 
                "error": "Failed to send. Please try again or contact us directly."
            }, status=500)
    
    # GET request - render the page
    return render(request, "pages/bulk.html")


def return_policy(request):
    return render(request, "pages/return_policy.html")


def privacy_policy(request):
    return render(request, "pages/privacy_policy.html")


def book_detail(request, slug):
    """Display individual book details"""
    book = get_object_or_404(Book, slug=slug)
    return render(request, "pages/book_detail.html", {"book": book})


def category_books(request, category):
    """Display books by category"""
    books = Book.objects.filter(category__iexact=category)
    return render(
        request,
        "pages/category_books.html",
        {"books": books, "category": category},
    )
