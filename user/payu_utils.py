import hashlib
import uuid
from django.conf import settings

def generate_payu_hash(params):
    """
    Generate hash for PayU payment request
    Sequence: key|txnid|amount|productinfo|firstname|email|udf1|udf2|udf3|udf4|udf5||||||SALT
    """
    salt = settings.PAYU_MERCHANT_SALT
    
    # Build hash string explicitly
    hash_string = ""
    hash_string += str(settings.PAYU_MERCHANT_KEY) + "|"
    hash_string += str(params.get('txnid', '')) + "|"
    hash_string += str(params.get('amount', '')) + "|"
    hash_string += str(params.get('productinfo', '')) + "|"
    hash_string += str(params.get('firstname', '')) + "|"
    hash_string += str(params.get('email', '')) + "|"
    hash_string += str(params.get('udf1', '')) + "|"
    hash_string += str(params.get('udf2', '')) + "|"
    hash_string += str(params.get('udf3', '')) + "|"
    hash_string += str(params.get('udf4', '')) + "|"
    hash_string += str(params.get('udf5', ''))
    hash_string += "||||||"  # Six empty fields
    hash_string += str(salt)
    
    # DEBUG: Log the exact string
    print(f"PAYU HASH INPUT: {hash_string}")
    
    hash_value = hashlib.sha512(hash_string.encode('utf-8')).hexdigest().lower()
    print(f"PAYU HASH OUTPUT: {hash_value}")
    return hash_value


def verify_payu_hash(response_data):
    """
    Verify hash from PayU response with EXACT reverse format:
    SALT|status||||||udf5|udf4|udf3|udf2|udf1|email|firstname|productinfo|amount|txnid|key
    """
    salt = settings.PAYU_MERCHANT_SALT
    
    # Build verification hash string
    hash_string = ""
    hash_string += str(salt) + "|"
    hash_string += str(response_data.get('status', '')) + "|"
    hash_string += "|||||"
    hash_string += str(response_data.get('udf5', '')) + "|"
    hash_string += str(response_data.get('udf4', '')) + "|"
    hash_string += str(response_data.get('udf3', '')) + "|"
    hash_string += str(response_data.get('udf2', '')) + "|"
    hash_string += str(response_data.get('udf1', '')) + "|"
    hash_string += str(response_data.get('email', '')) + "|"
    hash_string += str(response_data.get('firstname', '')) + "|"
    hash_string += str(response_data.get('productinfo', '')) + "|"
    hash_string += str(response_data.get('amount', '')) + "|"
    hash_string += str(response_data.get('txnid', '')) + "|"
    hash_string += str(response_data.get('key', ''))
    
    print(f"PAYU VERIFY HASH INPUT: {hash_string}")
    
    hash_value = hashlib.sha512(hash_string.encode('utf-8')).hexdigest().lower()
    print(f"PAYU VERIFY HASH OUTPUT: {hash_value}")
    return hash_value


def generate_transaction_id():
    """Generate unique transaction ID"""
    return f"TXN-{uuid.uuid4().hex[:12].upper()}"