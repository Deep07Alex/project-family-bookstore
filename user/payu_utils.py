# user/payu_utils.py - PRODUCTION READY
import hashlib
import uuid
from django.conf import settings
from django.core.cache import cache

def generate_payu_hash(params):
    """Generate hash for PayU payment request"""
    salt = settings.PAYU_MERCHANT_SALT
    
    # Build hash string
    hash_string = f"{settings.PAYU_MERCHANT_KEY}|"
    hash_string += f"{params.get('txnid', '')}|"
    hash_string += f"{params.get('amount', '')}|"
    hash_string += f"{params.get('productinfo', '')}|"
    hash_string += f"{params.get('firstname', '')}|"
    hash_string += f"{params.get('email', '')}|"
    hash_string += f"{params.get('udf1', '')}|"
    hash_string += f"{params.get('udf2', '')}|"
    hash_string += f"{params.get('udf3', '')}|"
    hash_string += f"{params.get('udf4', '')}|"
    hash_string += f"{params.get('udf5', '')}"
    hash_string += "||||||"  # Six empty fields
    hash_string += str(salt)
    
    # DEBUG: Log the exact string (disable in production)
    # print(f"PAYU HASH INPUT: {hash_string}")
    
    hash_value = hashlib.sha512(hash_string.encode('utf-8')).hexdigest().lower()
    # print(f"PAYU HASH OUTPUT: {hash_value}")
    return hash_value

def verify_payu_hash(response_data):
    """Verify hash from PayU response"""
    salt = settings.PAYU_MERCHANT_SALT
    
    # Build verification hash string
    hash_string = f"{salt}|"
    hash_string += f"{response_data.get('status', '')}|"
    hash_string += "|||||"
    hash_string += f"{response_data.get('udf5', '')}|"
    hash_string += f"{response_data.get('udf4', '')}|"
    hash_string += f"{response_data.get('udf3', '')}|"
    hash_string += f"{response_data.get('udf2', '')}|"
    hash_string += f"{response_data.get('udf1', '')}|"
    hash_string += f"{response_data.get('email', '')}|"
    hash_string += f"{response_data.get('firstname', '')}|"
    hash_string += f"{response_data.get('productinfo', '')}|"
    hash_string += f"{response_data.get('amount', '')}|"
    hash_string += f"{response_data.get('txnid', '')}|"
    hash_string += f"{response_data.get('key', '')}"
    
    # print(f"PAYU VERIFY HASH INPUT: {hash_string}")
    
    hash_value = hashlib.sha512(hash_string.encode('utf-8')).hexdigest().lower()
    # print(f"PAYU VERIFY HASH OUTPUT: {hash_value}")
    return hash_value

def generate_transaction_id():
    """Generate unique transaction ID and store in cache"""
    txnid = f"TXN-{uuid.uuid4().hex[:12].upper()}"
    # Store in cache with 30min expiry
    cache.set(f"txnid_key_{txnid}", True, 1800)
    return txnid

def verify_transaction_id(txnid):
    """Verify and consume txnid (one-time use)"""
    cache_key = f"txnid_key_{txnid}"
    if cache.get(cache_key):
        cache.delete(cache_key)  # One-time use
        return True
    return False