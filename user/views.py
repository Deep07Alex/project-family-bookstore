import hashlib
import re
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from django.views.decorators.cache import never_cache
from django.conf import settings
from django.core.cache import cache
from django.db import transaction, IntegrityError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from homepage.models import Book
from product_categories.models import Product
import requests

from .models import Order, OrderItem
from .payu_utils import generate_payu_hash, generate_transaction_id, verify_payu_hash
from .shiprocket_utils import ShiprocketAPI
from .utils import send_admin_order_notification, send_customer_order_confirmation

import json
import logging


logger = logging.getLogger(__name__)

# ==================== VALIDATION HELPERS ====================

def validate_phone_number(phone):
    """Validate Indian mobile number format"""
    pattern = re.compile(r'^[6-9]\d{9}$')
    return pattern.match(phone) is not None

def validate_pincode(pincode):
    """Validate 6-digit pincode"""
    return len(pincode) == 6 and pincode.isdigit()

def validate_cart_against_db(cart):
    """
    Validate cart items exist in DB and return validated cart with DB prices
    CRITICAL: Prevents price tampering
    """
    if not cart:
        return None, "Cart is empty"
    
    validated_cart = {}
    subtotal = Decimal('0.00')
    
    try:
        for key, item in cart.items():
            item_type = item.get('type')
            item_id = item.get('id')
            quantity = int(item.get('quantity', 1))
            
            if quantity < 1:
                raise ValueError("Invalid quantity")
            
            # Fetch actual object from DB
            if item_type == 'book':
                obj = Book.objects.get(id=item_id)
                item_price = obj.price
            elif item_type == 'product':
                obj = Product.objects.get(id=item_id)
                item_price = obj.price
            else:
                raise ValueError(f"Unknown item type: {item_type}")
            
            # TODO: Add stock validation when stock field is added to models
            # if hasattr(obj, 'stock') and obj.stock < quantity:
            #     raise ValueError(f"Insufficient stock for {obj.title}")
            
            validated_cart[key] = {
                'id': obj.id,
                'type': item_type,
                'title': obj.title,
                'price': float(item_price),  # Use DB price, not client price
                'image': obj.image.url if obj.image else '',
                'quantity': quantity
            }
            subtotal += item_price * quantity
        
        return validated_cart, subtotal
        
    except (Book.DoesNotExist, Product.DoesNotExist):
        return None, "Some items in your cart are no longer available"
    except Exception as e:
        logger.error(f"Cart validation error: {str(e)}")
        return None, str(e)

def calculate_order_totals(validated_cart, addons, payment_method):
    """Calculate totals server-side using validated data"""
    subtotal = sum(Decimal(str(item['price'])) * item['quantity'] for item in validated_cart.values())
    
    addon_prices = {"Bag": Decimal('30'), "bookmark": Decimal('20'), "packing": Decimal('20')}
    addon_total = sum(addon_prices.get(key, Decimal('0')) for key, selected in addons.items() if selected)
    
    total_books = sum(item['quantity'] for item in validated_cart.values())
    
    # Shipping logic
    if subtotal >= Decimal('499'):
        shipping = Decimal('0') if payment_method == 'payu' else Decimal('49')
    else:
        shipping = Decimal('40') if payment_method == 'payu' else Decimal('89')
    
    discount = Decimal('100') if total_books >= 10 else Decimal('0')
    total = subtotal + shipping + addon_total - discount
    
    return {
        'subtotal': subtotal,
        'addon_total': addon_total,
        'shipping': shipping,
        'discount': discount,
        'total': total,
        'total_books': total_books
    }

def _cleanup_session(request):
    """Atomic session cleanup - ALWAYS call before rendering"""
    keys_to_remove = [
        "cart", "cart_addons", "payu_txnid", "order_id", 
        "checkout_locked", "checkout_lock_time", "last_completed_order"
    ]
    for key in keys_to_remove:
        request.session.pop(key, None)
    request.session.modified = True

def _render_success(request, order):
    """Render success page with cache control"""
    response = render(request, "pages/payment_success.html", {
        "order": order,
        "shiprocket_order_id": order.shiprocket_order_id,
        "shiprocket_status": "Success" if order.shiprocket_shipment_created else "Manual processing required",
    })
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response

def _render_failure(request, error):
    """Render failure page with cache control"""
    response = render(request, "pages/payment_failure.html", {
        "error": error,
        "show_retry_button": True
    })
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response

# ==================== CART API ====================

def get_cart(request):
    """Get cart from session - CRITICAL HELPER"""
    return request.session.get("cart", {})

def save_cart(request, cart):
    """Save cart to session - CRITICAL HELPER"""
    request.session["cart"] = cart
    request.session.modified = True

@require_POST
def clear_cart(request):
    """Clear all items from cart"""
    request.session["cart"] = {}
    request.session["cart_addons"] = {}
    request.session.modified = True
    return JsonResponse({"success": True})

@require_POST
def add_to_cart(request):
    """Add item to cart via AJAX"""
    try:
        data = json.loads(request.body)
        quantity = int(data.get('quantity', 1))
        if quantity < 1:
            quantity = 1
        
        key = f"{data.get('type')}_{data.get('id')}"
        cart = get_cart(request)
        
        if key in cart:
            cart[key]["quantity"] += quantity
        else:
            cart[key] = {
                "id": data.get("id"),
                "type": data.get("type"),
                "title": data.get("title"),
                "price": float(data.get("price")),
                "image": data.get("image", ""),
                "quantity": quantity,
            }
        
        save_cart(request, cart)
        
        return JsonResponse({
            "success": True,
            "cart_count": sum(item["quantity"] for item in cart.values()),
            "total": sum(item["price"] * item["quantity"] for item in cart.values())
        })
    except Exception as e:
        logger.error(f"Add to cart error: {str(e)}")
        return JsonResponse({"success": False, "error": "Failed to add item"})

@require_POST
def update_cart_addons(request):
    """Update cart add-ons selection"""
    try:
        data = json.loads(request.body)
        addons = data.get("addons", {})
        request.session["cart_addons"] = addons
        request.session.modified = True
        
        addon_prices = {"Bag": 30, "bookmark": 20, "packing": 20}
        addon_total = sum(addon_prices.get(key, 0) for key, selected in addons.items() if selected)
        
        return JsonResponse({"success": True, "addon_total": addon_total})
    except Exception as e:
        logger.error(f"Update addons error: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)})

def get_cart_addons(request):
    """Get cart add-ons and their total"""
    addons = request.session.get("cart_addons", {})
    addon_prices = {"Bag": 30, "bookmark": 20, "packing": 20}
    addon_total = sum(addon_prices.get(key, 0) for key, selected in addons.items() if selected)
    return JsonResponse({"addons": addons, "addon_total": addon_total})

def get_cart_items(request):
    """Get cart items for display"""
    cart = get_cart(request)
    addons = request.session.get("cart_addons", {})
    
    addon_prices = {"Bag": 30, "bookmark": 20, "packing": 20}
    addon_total = sum(addon_prices.get(key, 0) for key, selected in addons.items() if selected)
    
    total_books = sum(item["quantity"] for item in cart.values())
    subtotal = sum(Decimal(str(item["price"])) * item["quantity"] for item in cart.values())
    shipping = Decimal('0') if subtotal >= Decimal('499') else Decimal('49.00')
    discount = Decimal('100') if total_books >= 10 else Decimal('0')
    total = subtotal + shipping + addon_total - discount
    
    return JsonResponse({
        "cart_count": sum(item["quantity"] for item in cart.values()),
        "items": list(cart.values()),
        "addons": addons,
        "addontotal": addon_total,
        "shipping": float(shipping),
        "discount": float(discount),
        "total": float(total),
        "totalbooks": total_books,
    })

@require_POST
def remove_from_cart(request):
    """Remove item from cart"""
    try:
        data = json.loads(request.body)
        cart = get_cart(request)
        key = data.get("key")
        
        if not key:
            return JsonResponse({"success": False, "error": "No key provided"}, status=400)
        
        if key in cart:
            del cart[key]
            save_cart(request, cart)
        else:
            return JsonResponse({"success": False, "error": "Item not found"}, status=404)
        
        return JsonResponse({
            "success": True,
            "cart_count": sum(item["quantity"] for item in cart.values()),
            "total": sum(item["price"] * item["quantity"] for item in cart.values())
        })
    except Exception as e:
        logger.error(f"Remove from cart error: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@require_POST
def update_cart_quantity(request):
    """Update item quantity"""
    try:
        data = json.loads(request.body)
        cart = get_cart(request)
        key = data.get("key")
        
        if not key:
            return JsonResponse({"success": False, "error": "No key provided"}, status=400)
        
        if key in cart:
            quantity = int(data.get("quantity", 1))
            if quantity <= 0:
                del cart[key]
            else:
                cart[key]["quantity"] = quantity
            save_cart(request, cart)
        else:
            return JsonResponse({"success": False, "error": "Item not found"}, status=404)
        
        return JsonResponse({
            "success": True,
            "cart_count": sum(item["quantity"] for item in cart.values()),
            "total": sum(item["price"] * item["quantity"] for item in cart.values())
        })
    except ValueError:
        return JsonResponse({"success": False, "error": "Invalid quantity"}, status=400)
    except Exception as e:
        logger.error(f"Update quantity error: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@require_GET
def check_checkout_lock(request):
    """Check if checkout is locked (with stale lock cleanup)"""
    lock_time = request.session.get("checkout_lock_time")
    
    if lock_time:
        lock_datetime = datetime.fromtimestamp(lock_time, tz=timezone.utc)
        if datetime.now(timezone.utc) - lock_datetime > timedelta(minutes=5):
            # Clear stale lock
            request.session.pop("checkout_locked", None)
            request.session.pop("checkout_lock_time", None)
            request.session.modified = True
            return JsonResponse({"locked": False, "stale_cleared": True})
    
    is_locked = bool(request.session.get("checkout_locked"))
    return JsonResponse({"locked": is_locked})

# ==================== CHECKOUT ====================

@never_cache
def checkout(request):
    """Display checkout page"""
    try:
        # Clear stale locks
        lock_time = request.session.get("checkout_lock_time")
        if lock_time:
            lock_datetime = datetime.fromtimestamp(lock_time, tz=timezone.utc)
            if datetime.now(timezone.utc) - lock_datetime > timedelta(minutes=5):
                request.session.pop("checkout_locked", None)
                request.session.pop("checkout_lock_time", None)
                request.session.modified = True
        
        # Check if checkout is locked (payment in progress)
        if request.session.get("checkout_locked"):
            return _render_failure(request, "Payment session is active. Please complete it or wait a few minutes.")
        
        cart = request.session.get("cart", {})
        if not cart:
            return HttpResponse("Your cart is empty. Please add books before checkout.", status=400)
        
        addons = request.session.get("cart_addons", {})
        
        # Calculate totals
        subtotal = sum(Decimal(str(item["price"])) * item["quantity"] for item in cart.values())
        addon_prices = {"Bag": Decimal('30'), "bookmark": Decimal('20'), "packing": Decimal('20')}
        addon_total = sum(addon_prices.get(key, Decimal('0')) for key, selected in addons.items() if selected)
        total_books = sum(item["quantity"] for item in cart.values())
        shipping = Decimal('0') if subtotal >= Decimal('499') else Decimal('49.00')
        discount = Decimal('100') if total_books >= 10 else Decimal('0')
        total = subtotal + shipping + addon_total - discount
        
        cart_items = [{
            "title": item["title"],
            "price": float(item["price"]),
            "quantity": item["quantity"],
            "image": item.get("image", ""),
            "type": item["type"],
        } for item in cart.values()]
        
        return render(request, "checkout.html", {
            "cart_items": cart_items,
            "subtotal": float(subtotal),
            "shipping": float(shipping),
            "discount": float(discount),
            "addon_total": float(addon_total),
            "total": float(total),
            "total_books": total_books,
        })
        
    except Exception as e:
        logger.error(f"Checkout error: {str(e)}", exc_info=True)
        return HttpResponse(f"Checkout error: {str(e)}", status=500)

# ==================== PAYMENT PROCESSING ====================

@require_POST
def initiate_payu_payment(request):
    """Initiate PayU payment with server-side validation"""
    try:
        data = json.loads(request.body)
        
        # Validate input
        required_fields = ['fullname', 'phone', 'email', 'address', 'city', 'state', 'pincode']
        for field in required_fields:
            if not data.get(field, '').strip():
                return JsonResponse({"success": False, "error": f"{field} is required"})
        
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip()
        pincode = data.get('pincode', '').strip()
        
        if not validate_phone_number(phone):
            return JsonResponse({"success": False, "error": "Invalid mobile number"})
        if not validate_pincode(pincode):
            return JsonResponse({"success": False, "error": "Invalid pincode"})
        
        # Lock checkout
        request.session["checkout_locked"] = True
        request.session["checkout_lock_time"] = datetime.now(tz=timezone.utc).timestamp()
        
        # Validate cart against DB (CRITICAL: prevents price tampering)
        cart = request.session.get("cart", {})
        addons = request.session.get("cart_addons", {})
        
        validated_cart, db_subtotal = validate_cart_against_db(cart)
        if validated_cart is None:
            return JsonResponse({"success": False, "error": db_subtotal})
        
        # Use validated data for calculations
        totals = calculate_order_totals(validated_cart, addons, 'payu')
        
        # Create order
        order = Order.objects.create(
            email=email,
            phone_number=phone,
            full_name=data.get('fullname', '').strip(),
            address=data.get('address', '').strip(),
            city=data.get('city', '').strip(),
            state=data.get('state', '').strip(),
            pin_code=pincode,
            delivery_type=data.get('delivery', 'Standard (3-6 days)'),
            payment_method='payu',
            subtotal=totals['subtotal'],
            shipping=totals['shipping'],
            discount=totals['discount'],
            total=totals['total'],
            status="pending_payment",
        )
        
        # Create order items
        for item in validated_cart.values():
            OrderItem.objects.create(
                order=order,
                item_type=item['type'],
                item_id=item['id'],
                title=item['title'],
                price=Decimal(str(item['price'])),
                quantity=item['quantity'],
                image_url=item.get('image', ''),
            )
        
        # Add addons
        addon_names = {"Bag": "Bag", "bookmark": "Bookmark", "packing": "Packing"}
        addon_prices = {"Bag": Decimal('30'), "bookmark": Decimal('20'), "packing": Decimal('20')}
        for addon_key, selected in addons.items():
            if selected and addon_key in addon_names:
                OrderItem.objects.create(
                    order=order,
                    item_type="addon",
                    item_id=0,
                    title=addon_names[addon_key],
                    price=addon_prices[addon_key],
                    quantity=1,
                    image_url="",
                )
        
        # Generate unique transaction ID
        txnid = generate_transaction_id()
        
        # Store txnid in cache for idempotency (30 min expiry)
        cache.set(f"txnid_{txnid}", str(order.id), 1800)
        
        payu_params = {
            "key": settings.PAYU_MERCHANT_KEY,
            "txnid": txnid,
            "amount": f"{totals['total']:.2f}",
            "productinfo": f"Order #{order.id}",
            "firstname": data.get('fullname', '').strip()[:50],
            "email": email,
            "phone": phone,
            "surl": request.build_absolute_uri("/payment/success/"),
            "furl": request.build_absolute_uri("/payment/failure/"),
            "udf1": str(order.id),
            "udf2": str(totals['discount']),
            "udf3": str(totals['total_books']),
            "udf4": data.get('delivery', 'Standard (3-6 days)'),
            "udf5": str(totals['shipping']),
        }
        
        payu_params["hash"] = generate_payu_hash(payu_params)
        
        request.session["payu_txnid"] = txnid
        request.session["order_id"] = order.id
        
        return JsonResponse({
            "success": True,
            "payu_url": settings.PAYU_TEST_URL if getattr(settings, "PAYU_TEST_MODE", True) else settings.PAYU_PROD_URL,
            "payu_params": payu_params,
        })
        
    except Exception as e:
        logger.error(f"Payment initiation error: {str(e)}", exc_info=True)
        # Clear lock on error
        request.session.pop("checkout_locked", None)
        request.session.pop("checkout_lock_time", None)
        return JsonResponse({"success": False, "error": str(e)})

@require_POST
def place_cod_order(request):
    """Create COD order with server-side validation"""
    try:
        data = json.loads(request.body)
        
        # Validate input
        required_fields = ['fullname', 'phone', 'email', 'address', 'city', 'state', 'pincode']
        for field in required_fields:
            if not data.get(field, '').strip():
                return JsonResponse({"success": False, "error": f"{field} is required"})
        
        phone = data.get('phone', '').strip()
        pincode = data.get('pincode', '').strip()
        
        if not validate_phone_number(phone):
            return JsonResponse({"success": False, "error": "Invalid mobile number"})
        if not validate_pincode(pincode):
            return JsonResponse({"success": False, "error": "Invalid pincode"})
        
        # Lock checkout
        request.session["checkout_locked"] = True
        request.session["checkout_lock_time"] = datetime.now(tz=timezone.utc).timestamp()
        
        # Validate cart against DB
        cart = request.session.get("cart", {})
        addons = request.session.get("cart_addons", {})
        
        validated_cart, db_subtotal = validate_cart_against_db(cart)
        if validated_cart is None:
            return JsonResponse({"success": False, "error": db_subtotal})
        
        totals = calculate_order_totals(validated_cart, addons, 'cod')
        
        # Create order
        order = Order.objects.create(
            email=data.get('email', '').strip(),
            phone_number=phone,
            full_name=data.get('fullname', '').strip(),
            address=data.get('address', '').strip(),
            city=data.get('city', '').strip(),
            state=data.get('state', '').strip(),
            pin_code=pincode,
            delivery_type=data.get('delivery', 'Standard (3-6 days)'),
            payment_method='cod',
            subtotal=totals['subtotal'],
            shipping=totals['shipping'],
            discount=totals['discount'],
            total=totals['total'],
            status="processing",
        )
        
        # Create order items
        for item in validated_cart.values():
            OrderItem.objects.create(
                order=order,
                item_type=item['type'],
                item_id=item['id'],
                title=item['title'],
                price=Decimal(str(item['price'])),
                quantity=item['quantity'],
                image_url=item.get('image', ''),
            )
        
        # Add addons
        addon_names = {"Bag": "Bag", "bookmark": "Bookmark", "packing": "Packing"}
        addon_prices = {"Bag": Decimal('30'), "bookmark": Decimal('20'), "packing": Decimal('20')}
        for addon_key, selected in addons.items():
            if selected and addon_key in addon_names:
                OrderItem.objects.create(
                    order=order,
                    item_type="addon",
                    item_id=0,
                    title=addon_names[addon_key],
                    price=addon_prices[addon_key],
                    quantity=1,
                    image_url="",
                )
        
        # Create Shiprocket shipment
        try:
            shiprocket = ShiprocketAPI()
            shiprocket_success, shiprocket_result = shiprocket.create_order(order, order.items.all())
            if shiprocket_success:
                order.shiprocket_order_id = shiprocket_result.get("order_id")
                order.awb_number = shiprocket_result.get("awb_code", "")
                order.courier_name = shiprocket_result.get("courier_name", "")
                order.label_url = shiprocket_result.get("label_url")
                order.shiprocket_shipment_created = True
                order.save()
        except Exception as e:
            logger.error(f"Shiprocket COD error: {str(e)}", exc_info=True)
            # Don't fail the order, allow manual processing
        
        # Send notifications
        send_admin_order_notification(order, order.items.all())
        send_customer_order_confirmation(order, order.items.all())
        order.customer_notified = True
        order.save()
        
        # Clear session
        _cleanup_session(request)
        
        return JsonResponse({
            "success": True,
            "redirect_url": f"/payment/success/?order_id={order.id}",
            "shiprocket_success": shiprocket_success
        })
        
    except Exception as e:
        logger.error(f"COD order error: {str(e)}", exc_info=True)
        # Clear lock on error
        request.session.pop("checkout_locked", None)
        request.session.pop("checkout_lock_time", None)
        return JsonResponse({"success": False, "error": str(e)})

# ==================== PAYMENT SUCCESS/FAILURE ====================

@never_cache
@csrf_exempt
def payment_success(request):
    """
    Idempotent payment success handler
    CRITICAL: Prevents duplicate processing and session replay
    """
    # Clear checkout lock immediately
    request.session.pop("checkout_locked", None)
    request.session.pop("checkout_lock_time", None)
    
    if request.method == "POST":
        return _handle_payu_callback(request)
    elif request.method == "GET":
        return _handle_success_page(request)
    
    return redirect('/')

def _handle_payu_callback(request):
    """Process PayU callback with idempotency"""
    response_data = request.POST.dict()
    received_hash = response_data.get("hash", "")
    calculated_hash = verify_payu_hash(response_data)
    
    if received_hash != calculated_hash:
        logger.error(f"PayU hash mismatch. Received: {received_hash}, Calculated: {calculated_hash}")
        _cleanup_session(request)
        return _render_failure(request, "Security verification failed")
    
    order_id = response_data.get("udf1")
    status = response_data.get("status")
    payment_id = response_data.get("mihpayid", "")
    txnid = response_data.get("txnid")
    
    # Verify txnid not reused (idempotency)
    cache_key = f"processed_txnid_{txnid}"
    if cache.get(cache_key):
        logger.warning(f"Duplicate txnid: {txnid}")
        _cleanup_session(request)
        try:
            order = Order.objects.get(id=order_id)
            return redirect(f'/order-tracking/?order_id={order.id}')
        except Order.DoesNotExist:
            return redirect('/')
    
    try:
        with transaction.atomic():
            # Lock order row
            order = Order.objects.select_for_update().get(id=order_id)
            
            # Check if already processed
            if order.status != "pending_payment":
                logger.info(f"Order {order_id} already processed")
                cache.set(cache_key, True, 3600)  # Mark as processed
                _cleanup_session(request)
                return redirect(f'/order-tracking/?order_id={order.id}')
            
            if status == "success":
                # Update order
                order.payment_id = payment_id
                order.payu_txnid = txnid
                order.status = "processing"
                order.save()
                
                # Create Shiprocket shipment (idempotent)
                if not order.shiprocket_shipment_created:
                    try:
                        shiprocket = ShiprocketAPI()
                        shiprocket_success, shiprocket_result = shiprocket.create_order(order, order.items.all())
                        if shiprocket_success:
                            order.shiprocket_order_id = shiprocket_result.get("order_id")
                            order.awb_number = shiprocket_result.get("awb_code", "")
                            order.courier_name = shiprocket_result.get("courier_name", "")
                            order.label_url = shiprocket_result.get("label_url")
                            order.shiprocket_shipment_created = True
                            order.save()
                    except Exception as shiprocket_error:
                        logger.error(f"Shiprocket error: {str(shiprocket_error)}", exc_info=True)
                
                # Send notifications (idempotent)
                if not order.customer_notified:
                    send_admin_order_notification(order, order.items.all())
                    send_customer_order_confirmation(order, order.items.all())
                    order.customer_notified = True
                    order.save()
                
                # Mark txnid as processed
                cache.set(cache_key, True, 3600)
                
                # CRITICAL: Clear session BEFORE rendering
                _cleanup_session(request)
                
                return _render_success(request, order)
            else:
                # Payment failed
                order.delete()  # Remove pending order
                _cleanup_session(request)
                return _render_failure(request, f"Payment status: {status}")
                
    except Order.DoesNotExist:
        _cleanup_session(request)
        return _render_failure(request, "Order not found")
    except IntegrityError as e:
        logger.error(f"Integrity error processing payment: {e}")
        _cleanup_session(request)
        return _render_failure(request, "Duplicate processing prevented")

def _handle_success_page(request):
    """Handle GET request to success page (COD or PayU redirect)"""
    order_id = request.GET.get("order_id")
    if not order_id:
        return redirect('/')
    
    try:
        order = Order.objects.get(id=order_id)
        
        # Verify order belongs to this session or is completed
        session_order_id = request.session.get("last_completed_order")
        if str(order.id) != str(session_order_id) and order.status == "pending_payment":
            # Prevent accessing unfinished orders
            return redirect(f'/order-tracking/?order_id={order.id}')
        
        # Clear session
        _cleanup_session(request)
        
        return _render_success(request, order)
        
    except Order.DoesNotExist:
        return redirect('/')

@never_cache
@csrf_exempt
def payment_failure(request):
    """Handle payment failure with proper cleanup"""
    # Clear checkout lock
    request.session.pop("checkout_locked", None)
    request.session.pop("checkout_lock_time", None)
    
    if request.method == "POST":
        response_data = request.POST.dict()
        order_id = response_data.get("udf1")
        
        if order_id:
            try:
                # Delete pending order
                with transaction.atomic():
                    order = Order.objects.select_for_update().get(id=order_id, status="pending_payment")
                    order.delete()
                    logger.info(f"Deleted failed order #{order_id}")
            except (Order.DoesNotExist, IntegrityError):
                pass
        
        _cleanup_session(request)
        return _render_failure(request, response_data.get("error_Message", "Payment failed"))
    
    # GET request
    _cleanup_session(request)
    return _render_failure(request, "Payment cancelled or failed")

# ==================== SESSION CLEANUP ====================

@require_POST
def clear_checkout_lock(request):
    """Manual endpoint to clear stuck checkout lock"""
    request.session.pop("checkout_locked", None)
    request.session.pop("checkout_lock_time", None)
    request.session.pop("payu_txnid", None)
    request.session.pop("order_id", None)
    request.session.modified = True
    
    logger.info(f"Manually cleared checkout lock for session {request.session.session_key}")
    return JsonResponse({"success": True, "message": "Lock cleared. You can retry checkout."})

@require_POST
def clear_payment_session(request):
    """Clear payment-related session data"""
    _cleanup_session(request)
    return JsonResponse({"success": True})

# ==================== ORDER TRACKING ====================

def track_order(request):
    """Public order tracking page"""
    order_id = request.GET.get('order_id')
    order = None
    tracking_info = None
    
    if order_id:
        try:
            order = get_object_or_404(Order, id=order_id)
            
            if order.shiprocket_order_id:
                shiprocket = ShiprocketAPI()
                success, tracking_info = shiprocket.get_tracking_details(order.shiprocket_order_id)
                
                if success and tracking_info:
                    order.shiprocket_status = tracking_info.get('status')
                    order.awb_number = tracking_info.get('awb')
                    order.courier_name = tracking_info.get('courier')
                    order.save()
                    
        except Order.DoesNotExist:
            pass
    
    return render(request, 'pages/order_tracking.html', {
        'order': order,
        'tracking_info': tracking_info,
    })

@require_GET
def get_shiprocket_product_status(request):
    """Fetch product status from Shiprocket"""
    sku = request.GET.get('sku')
    if not sku:
        return JsonResponse({"success": False, "error": "SKU is required"})
    
    try:
        shiprocket = ShiprocketAPI()
        url = f"{shiprocket.BASE_URL}/products/show"
        headers = shiprocket.get_headers()
        params = {"sku": sku}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == 200 and data.get("data"):
            product = data["data"]
            return JsonResponse({
                "success": True,
                "sku": sku,
                "status": product.get("status"),
                "stock": product.get("stock"),
                "price": product.get("price"),
                "name": product.get("name"),
                "shiprocket_product_id": product.get("id"),
            })
        return JsonResponse({"success": False, "error": f"Product not found for SKU: {sku}"})
            
    except Exception as e:
        logger.error(f"Shiprocket product status error: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)})

@require_GET
def get_order_shiprocket_details(request, order_id):
    """Fetch complete Shiprocket order details"""
    try:
        order = get_object_or_404(Order, id=order_id)
        
        if not order.shiprocket_order_id:
            return JsonResponse({"success": False, "error": "No Shiprocket order ID found"})
        
        shiprocket = ShiprocketAPI()
        url = f"{shiprocket.BASE_URL}/orders/show/{order.shiprocket_order_id}"
        headers = shiprocket.get_headers()
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("order_id"):
            shiprocket_items = data.get("order_items", [])
            local_items = list(order.items.all())
            
            combined_items = []
            for i, shiprocket_item in enumerate(shiprocket_items):
                local_item = local_items[i] if i < len(local_items) else None
                combined_items.append({
                    "title": shiprocket_item.get("name"),
                    "book_id": local_item.item_id if local_item else "N/A",
                    "shiprocket_sku": shiprocket_item.get("sku"),
                    "quantity": shiprocket_item.get("quantity"),
                    "price": shiprocket_item.get("selling_price"),
                    "status": shiprocket_item.get("status", "Pending"),
                })
            
            return JsonResponse({
                "success": True,
                "shiprocket_order_id": data.get("order_id"),
                "status": data.get("status"),
                "awb_code": data.get("awb_code"),
                "courier_name": data.get("courier_name"),
                "label_url": data.get("label_url"),
                "items": combined_items
            })
        else:
            return JsonResponse({"success": False, "error": "Order not found in Shiprocket"})
            
    except Exception as e:
        logger.error(f"Shiprocket order details error: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)})

# ==================== SHIPPING QUOTE ====================

@require_POST
def calculate_shipping(request):
    """Calculate shipping rates for pincode"""
    try:
        data = json.loads(request.body)
        pincode = data.get("pincode", "").strip()
        
        if not validate_pincode(pincode):
            return JsonResponse({"success": False, "error": "Please enter a valid 6-digit PIN code"})
        
        cart = request.session.get("cart", {})
        if not cart:
            return JsonResponse({"success": False, "error": "Cart is empty"})
        
        total_items = sum(item["quantity"] for item in cart.values())
        total_weight = 0.5 * total_items
        package_length = 20
        package_width = 15
        package_height = max(2, total_items * 2)
        
        pickup_pincode = settings.SHIPROCKET_PICKUP_PINCODE.strip()  # Remove trailing space
        shiprocket = ShiprocketAPI()
        success, rates = shiprocket.calculate_shipping_rates(
            pickup_pincode=pickup_pincode,
            delivery_pincode=pincode,
            weight=total_weight,
            length=package_length,
            width=package_width,
            height=package_height,
        )
        
        if success and rates:
            formatted_rates = []
            for rate in rates[:3]:
                formatted_rates.append({
                    "courier_name": rate.get("courier_name", "Standard"),
                    "estimated_days": rate.get("estimated_delivery_days", "3-5"),
                    "rate": float(rate.get("freight_charge", 0)),
                    "total_charge": float(rate.get("total_charge", 0)),
                })
            
            return JsonResponse({
                "success": True,
                "rates": formatted_rates,
                "pickup_pincode": pickup_pincode,
            })
        else:
            # Fallback rates
            fallback_rates = [
                {"courier_name": "Standard Delivery", "estimated_days": "5-7", "rate": 49.0, "total_charge": 49.0},
                {"courier_name": "Express Delivery", "estimated_days": "2-3", "rate": 99.0, "total_charge": 99.0},
            ]
            
            return JsonResponse({
                "success": True,
                "rates": fallback_rates,
                "note": "Using standard rates",
                "pickup_pincode": pickup_pincode,
            })
    except Exception as e:
        logger.error(f"Shipping calculation error: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": "Unable to calculate shipping rates"})

# ==================== WEBHOOK ====================

@csrf_exempt
def shiprocket_webhook(request):
    """Handle Shiprocket webhook with security and idempotency"""
    logger.info("Shiprocket webhook received")
    
    if request.method != "POST":
        return JsonResponse({"status": "method not allowed"}, status=405)
    
    try:
        # IP whitelist check (add SHIPROCKET_IP_WHITELIST to settings)
        # client_ip = get_client_ip(request)
        # if client_ip not in settings.SHIPROCKET_IP_WHITELIST:
        #     return JsonResponse({"status": "unauthorized"}, status=401)
        
        # Signature verification
        incoming_token = request.headers.get("x-api-key")
        if not incoming_token or incoming_token != settings.SHIPROCKET_WEBHOOK_SECRET:
            logger.warning(f"Invalid webhook signature: {incoming_token}")
            return JsonResponse({"status": "unauthorized"}, status=401)
        
        data = json.loads(request.body)
        shiprocket_order_id = data.get('order_id')
        
        if not shiprocket_order_id:
            return JsonResponse({"status": "no order_id"}, status=400)
        
        # Idempotency check
        current_status = data.get('current_status', {}).get('name')
        if Order.objects.filter(shiprocket_order_id=shiprocket_order_id, shiprocket_status=current_status).exists():
            logger.info(f"Webhook already processed for {shiprocket_order_id}")
            return JsonResponse({"status": "already processed"}, status=200)
        
        # Update order
        updated = Order.objects.filter(shiprocket_order_id=shiprocket_order_id).update(
            shiprocket_status=current_status,
            awb_number=data.get('awb_code'),
            courier_name=data.get('courier_name'),
            tracking_data=data,
        )
        
        if updated:
            logger.info(f"Updated order {shiprocket_order_id} status to {current_status}")
            return JsonResponse({"status": "success"}, status=200)
        else:
            logger.warning(f"Order {shiprocket_order_id} not found for webhook update")
            return JsonResponse({"status": "order not found"}, status=404)
            
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

# ==================== UTILITY VIEWS ====================

def payment_redirect(request):
    """Common redirect page for payment processing"""
    mode = request.GET.get("mode", "payu")
    context = {"mode": mode}
    
    if mode == "cod":
        context["order_id"] = request.GET.get("order_id", "")
        return render(request, "payment_redirect.html", context)
    
    payu_url = request.session.get("payu_url")
    payu_params = request.session.get("payu_params")
    
    if not payu_url or not payu_params:
        return _render_failure(request, "Payment session expired. Please try again.")
    
    context["payu_url"] = payu_url
    context["params"] = payu_params
    return render(request, "payment_redirect.html", context)

def return_policy(request):
    return render(request, "pages/return_policy.html")

def privacy_policy(request):
    return render(request, "pages/privacy_policy.html")