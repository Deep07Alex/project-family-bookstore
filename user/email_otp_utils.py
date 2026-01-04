# user/email_otp_utils.py
import random
import string
from django.core.mail import send_mail
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


def generate_otp(length=6):
    """Generate a random 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=length))


def send_email_otp(email, otp):
    """Send OTP to email using Django's email backend"""
    try:
        subject = 'Your Family BookStore Verification Code'

        message = f"""
Hello!

Your verification code for Family BookStore is:

{otp}

This code will expire in 10 minutes.

If you didn't request this, please ignore this email.

Best regards,
Family BookStore Team
        """.strip()

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        logger.info(f"OTP sent to {email}")
        return True, "OTP sent successfully"

    except Exception as e:
        logger.error(f"Failed to send OTP to {email}: {str(e)}")
        return False, str(e)


def store_otp_in_cache(email, otp, timeout=600):
    """Store OTP in cache for 10 minutes"""
    cache_key = f"otp_{email}"
    cache.set(cache_key, otp, timeout)
    return True


def verify_otp_from_cache(email, otp):
    """Verify OTP from cache"""
    cache_key = f"otp_{email}"
    cached_otp = cache.get(cache_key)

    if cached_otp and cached_otp == otp:
        cache.delete(cache_key)
        return True
    return False
