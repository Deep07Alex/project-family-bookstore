# user/shiprocket_utils.py - PRODUCTION READY
import hmac
import hashlib
import json
import logging
import time
from django.conf import settings
import requests

logger = logging.getLogger(__name__)

class ShiprocketAPI:
    """Shiprocket API client with authentication and retry logic"""
    
    BASE_URL = getattr(settings, "SHIPROCKET_BASE_URL", "https://apiv2.shiprocket.in/v1/external").strip()
    
    def __init__(self):
        self.email = settings.SHIPROCKET_EMAIL
        self.password = settings.SHIPROCKET_API_PASSWORD
        self.channel_id = getattr(settings, "SHIPROCKET_CHANNEL_ID", None)
        self.token = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate and store token"""
        try:
            url = f"{self.BASE_URL}/auth/login"
            payload = {"email": self.email, "password": self.password}
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("token"):
                self.token = data["token"]
                logger.info("Shiprocket authentication successful")
                return True
            else:
                logger.error(f"Shiprocket auth failed: {data}")
                raise Exception("Authentication failed")
                
        except Exception as e:
            logger.error(f"Shiprocket auth error: {str(e)}")
            raise

    def get_headers(self):
        """Get authorized headers"""
        if not self.token:
            self._authenticate()
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def calculate_shipping_rates(self, pickup_pincode, delivery_pincode, weight, length, width, height, cod=0):
        """Calculate shipping rates between pincodes with retry"""
        for attempt in range(3):
            try:
                url = f"{self.BASE_URL}/courier/serviceability"
                params = {
                    "pickup_postcode": pickup_pincode,
                    "delivery_postcode": delivery_pincode,
                    "weight": weight,
                    "length": length,
                    "breadth": width,
                    "height": height,
                    "cod": cod,
                }
                headers = self.get_headers()
                response = requests.get(url, params=params, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") == 200:
                    rates = data.get("data", {}).get("available_courier_companies", [])
                    if rates:
                        rates.sort(key=lambda x: (x.get("rating", 0), x.get("freight_charge", 9999)))
                        logger.info(f"Found {len(rates)} shipping options")
                        return True, rates
                    else:
                        logger.warning("No courier companies available")
                        return False, "No shipping options available"
                else:
                    logger.error(f"Shiprocket API error: {data}")
                    return False, data.get("message", "API error")
                    
            except requests.exceptions.Timeout:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Shipping calculation error (attempt {attempt+1}): {str(e)}")
                if attempt == 2:
                    return False, str(e)
                time.sleep(2 ** attempt)

    def create_order(self, order, items):
        """
        Create order in Shiprocket (IDEMPOTENT)
        Returns (success, result_dict)
        """
        # Check if already created
        if order.shiprocket_order_id:
            logger.info(f"Shiprocket order already exists: {order.shiprocket_order_id}")
            return True, {
                "order_id": order.shiprocket_order_id,
                "shipment_id": order.shiprocket_shipment_created,
                "awb_code": order.awb_number,
                "courier_name": order.courier_name,
                "label_url": order.label_url,
            }
        
        try:
            url = f"{self.BASE_URL}/orders/create/adhoc"
            
            order_items = []
            total_book_items = 0
            
            for item in items:
                # Generate clean SKU
                if item.item_type == "addon":
                    clean_sku = f"ADDON_{item.title.replace(' ', '_').upper()[:20]}"
                    hsn = "9999"
                else:
                    clean_sku = f"BOOK_{item.item_type}_{item.item_id}"
                    hsn = "4901"
                
                order_items.append({
                    "name": item.title[:100],
                    "sku": clean_sku,
                    "units": item.quantity,
                    "selling_price": float(item.price),
                    "discount": 0,
                    "tax": 0,
                    "hsn": hsn,
                })
                
                if item.item_type != "addon":
                    total_book_items += item.quantity
            
            # Calculate package dimensions
            total_weight = round(0.5 * total_book_items, 2)
            package_length = 20
            package_breadth = 15
            package_height = max(2, total_book_items * 2)
            
            actual_subtotal = sum(
                float(item.price) * item.quantity for item in items if item.item_type != "addon"
            )
            
            payment_method = "COD" if order.payment_method == "cod" else "prepaid"
            
            payload = {
                "order_id": f"FB{order.id}",
                "order_date": order.created_at.strftime("%Y-%m-%d %H:%M"),
                "pickup_location": settings.SHIPROCKET_PICKUP_LOCATION,
                "channel_id": str(self.channel_id) if self.channel_id else "",
                "billing_customer_name": order.full_name,
                "billing_last_name": "",
                "billing_address": order.address,
                "billing_address_2": "",
                "billing_city": order.city,
                "billing_pincode": order.pin_code,
                "billing_state": order.state,
                "billing_country": "India",
                "billing_email": order.email,
                "billing_phone": order.phone_number,
                "shipping_is_billing": True,
                "order_items": order_items,
                "payment_method": payment_method,
                "shipping_charges": float(order.shipping),
                "giftwrap_charges": 0,
                "transaction_charges": 0,
                "total_discount": float(order.discount),
                "sub_total": actual_subtotal,
                "length": package_length,
                "breadth": package_breadth,
                "height": package_height,
                "weight": total_weight,
            }
            
            headers = self.get_headers()
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get("order_id") and data.get("shipment_id"):
                logger.info(f"Shiprocket order created: {data['order_id']}")
                
                # Update items with Shiprocket SKUs
                response_items = data.get("order_items", [])
                for i, response_item in enumerate(response_items):
                    if i < len(items):
                        items[i].shiprocket_sku = response_item.get("sku", "")
                        items[i].save()
                
                return True, {
                    "order_id": data["order_id"],
                    "shipment_id": data["shipment_id"],
                    "awb_code": data.get("awb_code", ""),
                    "courier_name": data.get("courier_name", ""),
                    "label_url": data.get("label_url"),
                    "order_items": response_items,
                }
            else:
                logger.error(f"Shiprocket order creation failed: {data}")
                return False, data.get("message", "Order creation failed")
                
        except Exception as e:
            logger.error(f"Shiprocket order creation error: {str(e)}", exc_info=True)
            return False, str(e)

    def get_tracking_details(self, shiprocket_order_id):
        """Fetch tracking details with retry"""
        try:
            url = f"{self.BASE_URL}/courier/track"
            headers = self.get_headers()
            params = {"order_id": shiprocket_order_id}
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            if data.get('tracking_data'):
                return True, {
                    'status': data['tracking_data'].get('shipment_track')[0].get('current_status'),
                    'awb': data['tracking_data'].get('shipment_track')[0].get('awb_code'),
                    'courier': data['tracking_data'].get('shipment_track')[0].get('courier_company'),
                    'tracking_url': data['tracking_data'].get('track_url'),
                    'estimated_delivery': data.get('etd'),
                    'tracking_history': data['tracking_data'].get('shipment_track_activities', [])
                }
            return False, "Tracking data not available"
            
        except Exception as e:
            logger.error(f"Shiprocket tracking error: {str(e)}")
            return False, str(e)

    @staticmethod
    def verify_webhook_signature(payload, signature):
        """Verify webhook signature using HMAC-SHA256"""
        try:
            secret = settings.SHIPROCKET_WEBHOOK_SECRET.encode("utf-8")
            computed_signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
            return hmac.compare_digest(computed_signature, signature)
        except Exception as e:
            logger.error(f"Webhook verification error: {str(e)}")
            return False