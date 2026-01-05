# demo/middleware.py
import time
from django.http import HttpRequest

class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-XSS-Protection'] = '1; mode=block'
        response['X-Frame-Options'] = 'DENY'
        response['Strict-Transport-Security'] = 'max-age=31536000'
        
        return response

class CacheControlMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request: HttpRequest):
        response = self.get_response(request)
        
        # Never cache payment/checkout pages
        if request.path.startswith(('/payment/', '/checkout/', '/api/initiate-payment')):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        return response

# Add to settings.py MIDDLEWARE
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'demo.middleware.SecurityHeadersMiddleware',  # Add this
    'demo.middleware.CacheControlMiddleware',      # Add this
    # ... existing middleware
]