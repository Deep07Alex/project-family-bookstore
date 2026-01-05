from django.urls import path
from . import views

urlpatterns = [
    # ============ PHASE 1: Cart Building ============
    path("cart/add/", views.add_to_cart, name="add_to_cart"),
    path("cart/items/", views.get_cart_items, name="get_cart_items"),
    path("cart/addons/get/", views.get_cart_addons, name="get_cart_addons"),
    path("cart/addons/update/", views.update_cart_addons, name="update_cart_addons"),
    path("cart/update/", views.update_cart_quantity, name="update_cart_quantity"),
    path("cart/remove/", views.remove_from_cart, name="remove_from_cart"),
    path("cart/clear/", views.clear_cart, name="clear_cart"),

    # ============ PHASE 2: Email Verification ============
    # OTP URLs REMOVED
    # path("api/send-email-otp/", views.send_email_otp, name="send_email_otp"),
    # path("api/verify-email-otp/", views.verify_email_otp, name="verify_email_otp"),

    # ============ PHASE 3: Checkout & Shipping ============
    path("checkout/", views.checkout, name="checkout"),
    path("api/check-checkout-lock/", views.check_checkout_lock, name="check_checkout_lock"),
    path("api/calculate-shipping/", views.calculate_shipping, name="calculate_shipping"),

    # ============ PHASE 4: Payment Processing ============
    path("api/initiate-payment/", views.initiate_payu_payment, name="initiate_payu_payment"),
    path("api/place-cod-order/", views.place_cod_order, name="place_cod_order"),
    path("payment/redirect/", views.payment_redirect, name="payment_redirect"),
    path("payment/success/", views.payment_success, name="payment_success"),
    path("payment/failure/", views.payment_failure, name="payment_failure"),

    # ============ PHASE 5: Session Cleanup ============
    path("api/clear-checkout-lock/", views.clear_checkout_lock, name="clear_checkout_lock"),
    path("api/clear-payment-session/", views.clear_payment_session, name="clear_payment_session"),

    # ============ PHASE 6: Order Tracking & Status ============
    path("order-tracking/", views.track_order, name="order_tracking"),
    path("api/shiprocket/product-status/", views.get_shiprocket_product_status, name="shiprocket_product_status"),
    path("api/shiprocket/order-details/<int:order_id>/", views.get_order_shiprocket_details, name="shiprocket_order_details"),
]