import requests
import json

BASE_URL = "https://apiv2.shiprocket.in/v1/external"

EMAIL = "aritrada420@gmail.com"
PASSWORD = "U12u!BK7PQoHo3%bjliA*gqbEllfp!KU"

login_url = f"{BASE_URL}/auth/login"
payload = {"email": EMAIL, "password": PASSWORD}

resp = requests.post(login_url, json=payload, timeout=15)
print("Status:", resp.status_code)
print("Body:", resp.text)

if resp.ok:
    data = resp.json()
    token = data.get("token")
    print("Token:", token)