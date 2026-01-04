from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.core.cache import cache
from datetime import datetime, timedelta, timezone
from .models import Order, OrderItem
import requests
from .payu_utils import (
    generate_payu_hash,
    generate_transaction_id,
    verify_payu_hash,
)
from .utils import (
    send_customer_order_confirmation,
    send_admin_order_notification,
)
from .shiprocket_utils import ShiprocketAPI
from .email_otp_utils import (
    generate_otp,
    send_email_otp as send_email_otp_util,
    store_otp_in_cache,
    verify_otp_from_cache,
)

import json
import logging

logger = logging.getLogger(__name__)


# ---------------- CART HELPERS ---------------- #
def get_cart(request):
    return request.session.get("cart", {})


def save_cart(request, cart):
    request.session["cart"] = cart
    request.session.modified = True


# ---------------- CART API ---------------- #
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
        key = f"{data.get('type')}_{data.get('id')}"
        cart = get_cart(request)
        
        quantity = int(data.get('quantity', 1))
        if quantity < 1:
            quantity = 1

        if key in cart:
            cart[key]["quantity"] += quantity
        else:
            cart[key] = {
                "id": data.get("id"),
                "type": data.get("type"),
                "title": data.get("title"),
                "price": float(data.get("price")),
                "image": data.get("image", ""),
                "quantity": quantity,  # Use actual quantity from frontend
            }

        save_cart(request, cart)

        return JsonResponse(
            {
                "success": True,
                "cart_count": sum(item["quantity"] for item in cart.values()),
                "total": sum(
                    item["price"] * item["quantity"] for item in cart.values()
                ),
            }
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@require_POST
def update_cart_addons(request):
    """Update cart add-ons selection"""
    try:
        data = json.loads(request.body)
        addons = data.get("addons", {})
        request.session["cart_addons"] = addons
        request.session.modified = True

        addon_prices = {"Bag": 30, "bookmark": 20, "packing": 20}
        addon_total = sum(
            addon_prices.get(key, 0) for key, selected in addons.items() if selected
        )

        return JsonResponse({"success": True, "addon_total": addon_total})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


def get_cart_addons(request):
    """Get cart add-ons and their total"""
    addons = request.session.get("cart_addons", {})
    addon_prices = {"Bag": 30, "bookmark": 20, "packing": 20}
    addon_total = sum(
        addon_prices.get(key, 0) for key, selected in addons.items() if selected
    )

    return JsonResponse({"addons": addons, "addon_total": addon_total})


def get_cart_items(request):
    """Get cart items for display"""
    cart = get_cart(request)
    items = list(cart.values())

    addons = request.session.get("cart_addons", {})
    addon_prices = {"Bag": 30, "bookmark": 20, "packing": 20}
    addon_total = sum(
        addon_prices.get(key, 0) for key, selected in addons.items() if selected
    )

    # Smart pricing
    total_books = sum(item["quantity"] for item in cart.values())
    product_total = sum(
        float(item["price"]) * item["quantity"] for item in cart.values()
    )
    shipping = 0 if product_total >= 499 else 49.00
    discount = 100 if total_books >= 10 else 0

    # Cart total must NOT include shipping — only products + addons
    cart_total = product_total + addon_total

    return JsonResponse(
        {
            "cart_count": sum(item["quantity"] for item in cart.values()),
            "items": items,
            "addons": addons,  # Add this line to include selected add-ons
            "addontotal": addon_total,
            "shipping": shipping,
            "discount": discount,
            "total": cart_total,
            "totalbooks": total_books,
        }
    )


@require_POST
def remove_from_cart(request):
    """Remove item from cart"""
    try:
        data = json.loads(request.body)
        cart = get_cart(request)
        key = data.get("key")

        if not key:
            return JsonResponse(
                {"success": False, "error": "No key provided"}, status=400
            )

        if key in cart:
            del cart[key]
            save_cart(request, cart)
        else:
            return JsonResponse(
                {"success": False, "error": "Item not found"}, status=404
            )

        return JsonResponse(
            {
                "success": True,
                "cart_count": sum(item["quantity"] for item in cart.values()),
                "total": sum(
                    item["price"] * item["quantity"] for item in cart.values()
                ),
            }
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_POST
def update_cart_quantity(request):
    """Update item quantity"""
    try:
        data = json.loads(request.body)
        cart = get_cart(request)
        key = data.get("key")

        if not key:
            return JsonResponse(
                {"success": False, "error": "No key provided"}, status=400
            )

        if key in cart:
            quantity = int(data.get("quantity", 1))
            if quantity <= 0:
                del cart[key]
            else:
                cart[key]["quantity"] = quantity
            save_cart(request, cart)
        else:
            return JsonResponse(
                {"success": False, "error": "Item not found"}, status=404
            )

        return JsonResponse(
            {
                "success": True,
                "cart_count": sum(item["quantity"] for item in cart.values()),
                "total": sum(
                    item["price"] * item["quantity"] for item in cart.values()
                ),
            }
        )
    except ValueError:
        return JsonResponse(
            {"success": False, "error": "Invalid quantity"}, status=400
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_GET
def check_checkout_lock(request):
    """
    FIXED: Check lock and auto-clear stale locks (>5 minutes)
    Returns: {"locked": false} if stale or no lock
    """
    lock_time = request.session.get("checkout_lock_time")
    
    if lock_time:
        lock_datetime = datetime.fromtimestamp(lock_time, tz=timezone.utc)
        # Reduce timeout to 5 minutes
        if datetime.now(timezone.utc) - lock_datetime > timedelta(minutes=5):
            # Clear stale lock
            request.session.pop("checkout_locked", None)
            request.session.pop("checkout_lock_time", None)
            request.session.modified = True
            return JsonResponse({"locked": False, "stale_cleared": True})
    
    is_locked = bool(request.session.get("checkout_locked"))
    return JsonResponse({"locked": is_locked})


# ---------------- CHECKOUT ---------------- #
def checkout(request):
    """
    FIXED: Aggressively clear stale locks on every visit
    Allow immediate retry after failure
    """
    try:
        # FORCE clear any locks older than 5 minutes
        lock_time = request.session.get("checkout_lock_time")
        if lock_time:
            lock_datetime = datetime.fromtimestamp(lock_time, tz=timezone.utc)
            if datetime.now(timezone.utc) - lock_datetime > timedelta(minutes=5):
                request.session.pop("checkout_locked", None)
                request.session.pop("checkout_lock_time", None)
                request.session.modified = True
        
        # If still locked (fresh lock), show failure page with retry button
        if request.session.get("checkout_locked"):
            return render(
                request,
                "pages/payment_failure.html",
                {
                    "error": "Payment session is active. Please complete it or wait a few minutes.",
                    "show_retry_button": True,  # Show manual retry button
                },
            )

        cart = request.session.get("cart", {})
        addons = request.session.get("cart_addons", {})

        if not cart:
            return HttpResponse(
                "Your cart is empty. Please add books before checkout.",
                status=400,
            )

        subtotal = sum(float(item["price"]) * item["quantity"] for item in cart.values())
        addon_prices = {"Bag": 30, "bookmark": 20, "packing": 20}
        addon_total = sum(
            addon_prices.get(key, 0) for key, selected in addons.items() if selected
        )
        total_books = sum(item["quantity"] for item in cart.values())
        shipping = 0 if subtotal >= 499 else 49.00
        discount = 100 if total_books >= 10 else 0
        total = subtotal + shipping + addon_total - discount

        cart_items = []
        for key, item in cart.items():
            cart_items.append({
                "title": item["title"],
                "price": float(item["price"]),
                "quantity": item["quantity"],
                "image": item.get("image", ""),
                "type": item["type"],
            })

        return render(
            request,
            "checkout.html",
            {
                "cart_items": cart_items,
                "subtotal": subtotal,
                "shipping": shipping,
                "discount": discount,
                "addon_total": addon_total,
                "total": total,
                "total_books": total_books,
            },
        )
    except Exception as e:
        logger.error(f"CHECKOUT ERROR: {str(e)}", exc_info=True)
        return HttpResponse(f"Checkout error: {str(e)}", status=500)


# ---------------- EMAIL OTP ---------------- #
@require_POST
def send_email_otp(request):
    """Send OTP to email"""
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()

        if not email or '@' not in email:
            return JsonResponse({'success': False, 'error': 'Invalid email address'})

        otp = generate_otp()
        success, message = send_email_otp_util(email, otp)
        if not success:
            logger.error(f"Failed to send OTP email: {message}")
            return JsonResponse({'success': False, 'error': 'Could not send OTP email'})

        store_otp_in_cache(email, otp)
        return JsonResponse({'success': True, 'message': 'OTP sent to your email'})
    except Exception as e:
        logger.error(f"Send email OTP error: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Failed to send OTP'})


@require_POST
def verify_email_otp(request):
    """Verify email OTP"""
    try:
        data = json.loads(request.body)
        email = data.get("email", "").strip()
        otp = data.get("otp", "").strip()

        if not email or not otp:
            return JsonResponse(
                {"success": False, "error": "Email and OTP required"}
            )

        if verify_otp_from_cache(email, otp):
            request.session["verified_email"] = email
            return JsonResponse(
                {"success": True, "message": "Email verified successfully"}
            )
        else:
            return JsonResponse(
                {"success": False, "error": "Invalid or expired OTP"}
            )
    except Exception as e:
        logger.error(f"Verify email OTP error: {str(e)}", exc_info=True)
        return JsonResponse(
            {"success": False, "error": "Verification failed"}
        )


# ---------------- PAYU PAYMENT ---------------- #
@require_POST
def initiate_payu_payment(request):
    """Initiate PayU payment after email verification"""
    try:
        verified_email = request.session.get("verified_email")
        if not verified_email:
            return JsonResponse(
                {"success": False, "error": "Please verify your email first"}
            )

        # 🔒 lock checkout once payment starts
        request.session["checkout_locked"] = True
        request.session["checkout_lock_time"] = datetime.now(tz=timezone.utc).timestamp()
        
        cart = request.session.get("cart", {})
        addons = request.session.get("cart_addons", {})
        data = json.loads(request.body)

        if not cart:
            return JsonResponse({"success": False, "error": "Cart is empty"})

        full_name = data.get("fullname", "").strip()
        phone = data.get("phone", "").strip()
        address = data.get("address", "").strip()
        city = data.get("city", "").strip()
        state = data.get("state", "").strip()
        pincode = data.get("pincode", "").strip()
        delivery_type = data.get("delivery", "Standard (3-6 days)")

        if not all([full_name, phone, address, city, state, pincode]):
            return JsonResponse(
                {"success": False, "error": "All fields are required"}
            )

        subtotal = sum(
            float(item["price"]) * item["quantity"] for item in cart.values()
        )

        addon_prices = {"Bag": 30, "bookmark": 20, "packing": 20}
        addon_total = sum(
            addon_prices.get(key, 0) for key, selected in addons.items() if selected
        )

        total_books = sum(item["quantity"] for item in cart.values())

        # base courier from Shiprocket (not used in pricing rules currently)
        base_courier_charge = float(data.get("shipping_cost", 0))

        # payment_method from frontend: "payu" or "cod"
        payment_method = data.get("payment_method", "payu")

        # Admin shipping rules:
        # - subtotal >= 499 & PayU -> shipping = 0
        # - subtotal >= 499 & COD -> shipping = 49
        # - subtotal < 499 & PayU -> shipping = 40
        # - subtotal < 499 & COD -> shipping = 89
        if subtotal >= 499:
            if payment_method == "payu":
                shipping = 0.0
            else:
                shipping = 49.0
        else:
            if payment_method == "payu":
                shipping = 40.0
            else:
                shipping = 40.0 + 49.0  # 89

        # If you ever want to add courier charge on top, uncomment:
        # shipping += base_courier_charge

        discount = 100 if total_books >= 10 else 0
        total = subtotal + shipping + addon_total - discount

        order = Order.objects.create(
            email=verified_email,
            verified_email=verified_email,
            phone_number=phone,
            full_name=full_name,
            address=address,
            city=city,
            state=state,
            pin_code=pincode,
            delivery_type=delivery_type,
            payment_method=payment_method,
            subtotal=subtotal,
            shipping=shipping,
            discount=discount,
            total=total,
            status="pending_payment",
        )

        for key, item in cart.items():
            OrderItem.objects.create(
                order=order,
                item_type=item["type"],
                item_id=item["id"],
                title=item["title"],
                price=float(item["price"]),
                quantity=item["quantity"],
                image_url=item.get("image", ""),
            )

        addon_names = {"Bag": "Bag", "bookmark": "Bookmark", "packing": "Packing"}
        for addon_key, selected in addons.items():
            if selected:
                OrderItem.objects.create(
                    order=order,
                    item_type="addon",
                    item_id=0,
                    title=addon_names[addon_key],
                    price=addon_prices[addon_key],
                    quantity=1,
                    image_url="",
                )

        txnid = generate_transaction_id()

        payu_params = {
            "key": settings.PAYU_MERCHANT_KEY,
            "txnid": txnid,
            "amount": f"{total:.2f}",
            "productinfo": f"Book Order {order.id}",
            "firstname": full_name[:50],
            "email": verified_email,
            "phone": phone,
            "surl": request.build_absolute_uri("/payment/success/"),
            "furl": request.build_absolute_uri("/payment/failure/"),
            "udf1": str(order.id),
            "udf2": str(discount),
            "udf3": str(total_books),
            "udf4": delivery_type,
            "udf5": str(shipping),
        }

        payu_params["hash"] = generate_payu_hash(payu_params)

        request.session["payu_txnid"] = txnid
        request.session["order_id"] = order.id

        return JsonResponse(
            {
                "success": True,
                "payu_url": settings.PAYU_TEST_URL
                if getattr(settings, "PAYU_TEST_MODE", True)
                else settings.PAYU_PROD_URL,
                "payu_params": payu_params,
            }
        )
    except Exception as e:
        logger.error(f"PAYMENT INIT ERROR: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})


@require_POST
def place_cod_order(request):
    """Create COD order without PayU and send to Shiprocket"""
    try:
        verified_email = request.session.get("verified_email")
        if not verified_email:
            return JsonResponse(
                {"success": False, "error": "Please verify your email first"}
            )

        # 🔒 lock checkout once COD processing starts
        request.session["checkout_locked"] = True
        request.session["checkout_lock_time"] = datetime.now(tz=timezone.utc).timestamp()
        
        cart = request.session.get("cart", {})
        addons = request.session.get("cart_addons", {})
        data = json.loads(request.body)

        if not cart:
            return JsonResponse({"success": False, "error": "Cart is empty"})

        full_name = data.get("fullname", "").strip()
        phone = data.get("phone", "").strip()
        address = data.get("address", "").strip()
        city = data.get("city", "").strip()
        state = data.get("state", "").strip()
        pincode = data.get("pincode", "").strip()
        delivery_type = data.get("delivery", "Standard (3-6 days)")

        if not all([full_name, phone, address, city, state, pincode]):
            return JsonResponse(
                {"success": False, "error": "All fields are required"}
            )

        # Same pricing logic as PayU view, but payment_method is cod
        subtotal = sum(
            float(item["price"]) * item["quantity"] for item in cart.values()
        )

        addon_prices = {"Bag": 30, "bookmark": 20, "packing": 20}
        addon_total = sum(
            addon_prices.get(key, 0) for key, selected in addons.items() if selected
        )

        total_books = sum(item["quantity"] for item in cart.values())
        payment_method = "cod"

        if subtotal >= 499:
            shipping = 49.0  # only handover charge
        else:
            shipping = 40.0 + 49.0  # 40 shipping + 49 handover

        discount = 100 if total_books >= 10 else 0
        total = subtotal + shipping + addon_total - discount

        order = Order.objects.create(
            email=verified_email,
            verified_email=verified_email,
            phone_number=phone,
            full_name=full_name,
            address=address,
            city=city,
            state=state,
            pin_code=pincode,
            delivery_type=delivery_type,
            payment_method=payment_method,
            subtotal=subtotal,
            shipping=shipping,
            discount=discount,
            total=total,
            status="processing",  # COD, payment on delivery
        )

        for key, item in cart.items():
            OrderItem.objects.create(
                order=order,
                item_type=item["type"],
                item_id=item["id"],
                title=item["title"],
                price=float(item["price"]),
                quantity=item["quantity"],
                image_url=item.get("image", ""),
            )

        addon_names = {"Bag": "Bag", "bookmark": "Bookmark", "packing": "Packing"}
        for addon_key, selected in addons.items():
            if selected:
                OrderItem.objects.create(
                    order=order,
                    item_type="addon",
                    item_id=0,
                    title=addon_names.get(addon_key, addon_key),
                    price=addon_prices[addon_key],
                    quantity=1,
                    image_url="",
                )

        # Create Shiprocket order as COD
        shiprocket_success = False
        shiprocket_data = None
        try:
            shiprocket = ShiprocketAPI()
            shiprocket_success, shiprocket_result = shiprocket.create_order(
                order, order.items.all()
            )
            if shiprocket_success:
                order.shiprocket_order_id = shiprocket_result.get("order_id")
                order.awb_number = shiprocket_result.get("awb_code") or ""
                order.courier_name = shiprocket_result.get("courier_name") or ""
                order.label_url = shiprocket_result.get("label_url")
                order.save()
                shiprocket_data = shiprocket_result
        except Exception as e:
            logger.error(f"Shiprocket COD order error: {str(e)}", exc_info=True)

        # Emails
        send_admin_order_notification(order, order.items.all())
        send_customer_order_confirmation(order, order.items.all())

        # Clear cart
        request.session.pop("cart", None)
        request.session.pop("cart_addons", None)
        request.session.pop("verified_email", None)

        # URL of your success page (GET version, not PayU POST)
        success_url = f"/payment/success/?order_id={order.id}"

        return JsonResponse(
            {"success": True, "redirect_url": success_url,
             "shiprocket_success": shiprocket_success}
        )

    except Exception as e:
        logger.error(f"place_cod_order error: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})


@csrf_exempt
def payment_success(request):
    """
    FIXED: Always clear lock on success (POST or GET)
    """
    # Clear lock immediately regardless of method
    request.session.pop("checkout_locked", None)
    request.session.pop("checkout_lock_time", None)
    
    if request.method == "POST":
        response_data = request.POST.dict()
        received_hash = response_data.get("hash", "")
        calculated_hash = verify_payu_hash(response_data)

        if received_hash == calculated_hash:
            order_id = response_data.get("udf1")
            status = response_data.get("status")
            payment_id = response_data.get("mihpayid", "")

            try:
                order = Order.objects.get(id=order_id)

                if status == "success":
                    order.status = "processing"
                    order.payment_id = payment_id
                    order.save()

                    items = order.items.all()
                    shiprocket_success = False
                    shiprocket_data = None

                    try:
                        shiprocket = ShiprocketAPI()
                        shiprocket_success, shiprocket_result = shiprocket.create_order(
                            order, items
                        )
                        if shiprocket_success:
                            order.shiprocket_order_id = shiprocket_result.get("order_id")
                            order.awb_number = shiprocket_result.get("awb_code") or ""
                            order.courier_name = shiprocket_result.get("courier_name") or ""
                            order.label_url = shiprocket_result.get("label_url")
                            if shiprocket_result.get("awb_code"):
                                order.status = "shipped"
                            else:
                                order.status = "processing"
                            order.save()
                            shiprocket_data = shiprocket_result
                    except Exception as shiprocket_error:
                        logger.error(f"Shiprocket error: {str(shiprocket_error)}", exc_info=True)

                    admin_success, _ = send_admin_order_notification(order, items)
                    customer_success, _ = send_customer_order_confirmation(order, items)

                    # Clear ALL session data
                    request.session.pop("cart", None)
                    request.session.pop("cart_addons", None)
                    request.session.pop("payu_txnid", None)
                    request.session.pop("order_id", None)
                    request.session.pop("verified_email", None)

                    # Add cache control headers to prevent back button issues
                    response = render(
                        request,
                        "pages/payment_success.html",
                        {
                            "order": order,
                            "shiprocket_data": shiprocket_data,
                            "shiprocket_order_id": order.shiprocket_order_id,
                            "shiprocket_status": "Success"
                            if shiprocket_success
                            else "Manual processing required",
                            "notification_sent": customer_success,
                        },
                    )
                    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                    response["Pragma"] = "no-cache"
                    response["Expires"] = "0"
                    return response
                    
                else:
                    order.delete()
                    return render(
                        request,
                        "pages/payment_failure.html",
                        {"error": f"Payment status: {status}", "show_retry_button": True},
                    )
            except Order.DoesNotExist:
                return render(
                    request,
                    "pages/payment_failure.html",
                    {"error": "Order not found", "show_retry_button": True},
                )
        else:
            return render(
                request,
                "pages/payment_failure.html",
                {"error": "Security verification failed", "show_retry_button": True},
            )

    if request.method == "GET":
        order_id = request.GET.get("order_id")
        if not order_id:
            return render(
                request,
                "pages/payment_failure.html",
                {"error": "Missing order id", "show_retry_button": True},
            )

        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return render(
                request,
                "pages/payment_failure.html",
                {"error": "Order not found", "show_retry_button": True},
            )

        request.session.pop("checkout_locked", None)
        request.session.pop("checkout_lock_time", None)
        
        response = render(
            request,
            "pages/payment_success.html",
            {
                "order": order,
                "shiprocket_order_id": order.shiprocket_order_id,
                "shiprocket_data": None,
                "shiprocket_status": "COD order placed",
                "notification_sent": True,
            },
        )
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response

    return render(
        request,
        "pages/payment_failure.html",
        {"error": "Invalid request method", "show_retry_button": True},
    )


@csrf_exempt
def payment_failure(request):
    """
    FIXED: Clear lock immediately on payment failure
    """
    #  Clear lock on ANY failure request
    request.session.pop("checkout_locked", None)
    request.session.pop("checkout_lock_time", None)

    if request.method == "POST":
        response_data = request.POST.dict()
        order_id = response_data.get("udf1")
        if order_id:
            try:
                Order.objects.get(id=order_id, status="pending_payment").delete()
            except Order.DoesNotExist:
                pass

        response = render(
            request,
            "pages/payment_failure.html",
            {
                "error": response_data.get("error_Message", "Payment failed"),
                "show_retry_button": True  #  Always show retry button
            },
        )
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response

    # GET request - show failure page with retry option
    response = render(
        request,
        "pages/payment_failure.html",
        {
            "error": "Payment cancelled or failed",
            "show_retry_button": True
        },
    )
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


@require_POST
def clear_payment_session(request):
    """Clear payment-related session data after successful payment"""
    request.session.pop("cart", None)
    request.session.pop("cart_addons", None)
    request.session.pop("payu_txnid", None)
    request.session.pop("order_id", None)
    request.session.pop("verified_email", None)
    request.session.pop("checkout_locked", None)
    request.session.pop("checkout_lock_time", None)
    return JsonResponse({"success": True})


@require_POST
def clear_checkout_lock(request):
    """
    NEW: Manual endpoint to clear stuck checkout lock
    Called when user clicks "Try Again" button
    """
    request.session.pop("checkout_locked", None)
    request.session.pop("checkout_lock_time", None)
    request.session.pop("payu_txnid", None)
    request.session.pop("order_id", None)
    request.session.pop("verified_email", None)
    request.session.modified = True
    
    logger.info(f"Manually cleared checkout lock for session {request.session.session_key}")
    return JsonResponse({"success": True, "message": "Lock cleared. You can retry checkout."})


def track_order(request):
    """
    Public order tracking page - customers can track their order status
    """
    order_id = request.GET.get('order_id')
    order = None
    tracking_info = None
    
    if order_id:
        try:
            order = get_object_or_404(Order, id=order_id)
            
            # If Shiprocket order exists, fetch latest tracking
            if order.shiprocket_order_id:
                shiprocket = ShiprocketAPI()
                success, tracking_info = shiprocket.get_tracking_details(
                    order.shiprocket_order_id
                )
                
                # Update local order with latest status
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
    """
    Fetch real-time product status from Shiprocket using SKU
    """
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
        return JsonResponse({
            "success": False,
            "error": f"Product not found for SKU: {sku}"
        })
            
    except Exception as e:
        logger.error(f"Shiprocket product status error: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)})


@require_GET
def get_order_shiprocket_details(request, order_id):
    """
    Fetch complete Shiprocket order details with SKU mapping
    """
    try:
        order = get_object_or_404(Order, id=order_id)
        
        if not order.shiprocket_order_id:
            return JsonResponse({
                "success": False,
                "error": "No Shiprocket order ID found"
            })

        shiprocket = ShiprocketAPI()
        url = f"{shiprocket.BASE_URL}/orders/show/{order.shiprocket_order_id}"
        headers = shiprocket.get_headers()
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("order_id"):
            # Map Shiprocket items with local items
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
            return JsonResponse({
                "success": False,
                "error": "Order not found in Shiprocket"
            })
            
    except Exception as e:
        logger.error(f"Shiprocket order details error: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)})


# ---------------- SHIPROCKET WEBHOOK ---------------- #
@csrf_exempt
def shiprocket_webhook(request):
    """Handle Shiprocket webhook for tracking updates"""
    logger = logging.getLogger(__name__)

    if request.method != "POST":
        return JsonResponse({"status": "method not allowed"}, status=405)

    try:
        incoming_token = request.headers.get("x-api-key")
        if not incoming_token or incoming_token != settings.SHIPROCKET_WEBHOOK_SECRET:
            return JsonResponse({"status": "unauthorized"}, status=401)

        data = json.loads(request.body)
        
        # Extract tracking data
        shiprocket_order_id = data.get('order_id')
        if not shiprocket_order_id:
            return JsonResponse({"status": "no order_id"}, status=400)

        # Update order with latest tracking
        Order.objects.filter(shiprocket_order_id=shiprocket_order_id).update(
            shiprocket_status=data.get('current_status', {}).get('name'),
            awb_number=data.get('awb_code'),
            courier_name=data.get('courier_name'),
            tracking_data=data,  
        )
        
        return JsonResponse({"status": "success"}, status=200)
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}", exc_info=True)
        return JsonResponse({"status": "error"}, status=500)


# ---------------- SHIPPING QUOTE ---------------- #
@require_POST
def calculate_shipping(request):
    """Calculate shipping rates for given pincode"""
    try:
        data = json.loads(request.body)
        pincode = data.get("pincode", "")

        if not pincode or len(pincode) != 6:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Please enter a valid 6-digit PIN code",
                }
            )

        cart = request.session.get("cart", {})
        if not cart:
            return JsonResponse(
                {"success": False, "error": "Cart is empty"}
            )

        total_items = sum(item["quantity"] for item in cart.values())
        total_weight = 0.5 * total_items
        package_length = 20
        package_width = 15
        package_height = 5 if total_items == 1 else total_items * 2

        pickup_pincode = settings.SHIPROCKET_PICKUP_PINCODE
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
                formatted_rates.append(
                    {
                        "courier_name": rate.get("courier_name", "Standard"),
                        "estimated_days": rate.get(
                            "estimated_delivery_days", "3-5"
                        ),
                        "rate": float(rate.get("freight_charge", 0)),
                        "total_charge": float(rate.get("total_charge", 0)),
                    }
                )

            return JsonResponse(
                {
                    "success": True,
                    "rates": formatted_rates,
                    "pickup_pincode": pickup_pincode,
                }
            )
        else:
            fallback_rates = [
                {
                    "courier_name": "Standard Delivery",
                    "estimated_days": "5-7",
                    "rate": 49.0,
                    "total_charge": 49.0,
                },
                {
                    "courier_name": "Express Delivery",
                    "estimated_days": "2-3",
                    "rate": 99.0,
                    "total_charge": 99.0,
                },
            ]

            return JsonResponse(
                {
                    "success": True,
                    "rates": fallback_rates,
                    "note": "Using standard rates",
                    "pickup_pincode": pickup_pincode,
                }
            )
    except Exception as e:
        logger.error(f"Shipping calculation error: {str(e)}", exc_info=True)
        return JsonResponse(
            {"success": False, "error": "Unable to calculate shipping rates"}
        )


def return_policy(request):
    return render(request, "pages/return_policy.html")


def privacy_policy(request):
    return render(request, "pages/privacy_policy.html")


# ---------------- NEW: COMMON REDIRECT VIEW ---------------- #
def payment_redirect(request):
    """
    Common redirect page:
    - mode=payu: show spinner + auto-submit PayU form
    - mode=cod: show spinner + then go to success page
    """
    mode = request.GET.get("mode", "payu")
    context = {"mode": mode}

    if mode == "cod":
        context["order_id"] = request.GET.get("order_id", "")
        return render(request, "payment_redirect.html", context)

    payu_url = request.session.get("payu_url")
    payu_params = request.session.get("payu_params")

    if not payu_url or not payu_params:
        return render(
            request,
            "pages/payment_failure.html",
            {"error": "Payment session expired. Please try again.", "show_retry_button": True},
        )

    context["payu_url"] = payu_url
    context["params"] = payu_params
    return render(request, "payment_redirect.html", context)