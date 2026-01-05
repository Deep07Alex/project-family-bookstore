import logging
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

logger = logging.getLogger(__name__)

def send_admin_order_notification(order, items):
    """Send detailed email to admin about new order"""
    try:
        items_details = "\n".join([
            f"• {item.title} (Qty: {item.quantity}, Price: ₹{item.price})"
            for item in items
        ])
        
        subject = f'🛒 New Order Received - #{order.id}'
        
        message = f"""
Hello Admin,

A new order has been placed on Family BookStore!

═══════════════════════════════════════

📋 ORDER DETAILS:
Order ID: #{order.id}
Order Date: {order.created_at.strftime('%d-%b-%Y %I:%M %p')}
Status: {order.status.upper()}
Payment Method: {order.payment_method}

═══════════════════════════════════════

👤 CUSTOMER DETAILS:
Name: {order.full_name}
Phone: {order.phone_number}
Email: {order.email}

📍 SHIPPING ADDRESS:
{order.address}
{order.city}, {order.state} - {order.pin_code}

═══════════════════════════════════════

📦 ORDER ITEMS:
{items_details}

═══════════════════════════════════════

💳 PAYMENT SUMMARY:
Subtotal: ₹{order.subtotal}
Shipping: ₹{order.shipping}
Discount: ₹{order.discount}
TOTAL: ₹{order.total}

═══════════════════════════════════════

Delivery Type: {order.delivery_type}

Thank you!
Family BookStore System
        """.strip()
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_ORDER_EMAIL],
            fail_silently=False,
        )
        
        logger.info(f"Admin notification sent for Order #{order.id}")
        return True, "Admin email sent successfully"
        
    except Exception as e:
        logger.error(f"Admin notification failed: {str(e)}")
        return False, str(e)


def send_customer_order_confirmation(order, items):
    """Send order confirmation to customer via EMAIL"""
    try:
        item_names = [item.title for item in items[:3]]
        items_text = ", ".join(item_names)
        if len(items) > 3:
            items_text += f" and {len(items) - 3} more"
        
        message = f"""
🏪 Family BookStore - Order Confirmed!

═══════════════════════════════════════

📋 ORDER DETAILS:
Order ID: #{order.id}
Items: {items_text}
Total: ₹{order.total}
Delivery Address: {order.address}, {order.city}, {order.state} - {order.pin_code}

📦 Estimated Delivery: 3-6 business days

═══════════════════════════════════════

Need help? Contact us at /contactinformation/

Thank you for shopping with us! 😊
        """.strip()
        
        send_mail(
            subject=f'Order Confirmed - #{order.id} - Family BookStore',
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.email],
            fail_silently=False,
        )
        
        logger.info(f"Customer confirmation sent via email for Order #{order.id}")
        return True, "Customer email sent successfully"
        
    except Exception as e:
        logger.error(f"Customer notification failed: {str(e)}")
        return False, str(e)