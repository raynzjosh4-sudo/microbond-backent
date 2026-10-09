import uuid
import requests

PRIMARY_KEY = "14fd26adf1044f2d9ca1e488ffbbd4db"
BASE_URL = "https://sandbox.momodeveloper.mtn.com/v1_0"

api_user_id = str(uuid.uuid4())
print(f"MTN_API_USER={api_user_id}")
print(f"MTN_SUBSCRIPTION_KEY={PRIMARY_KEY}")

headers = {
    "X-Reference-Id": api_user_id,
    "Ocp-Apim-Subscription-Key": PRIMARY_KEY,
    "Content-Type": "application/json"
}
body = {"providerCallbackHost": "https://webhook.site/placeholder"}

response = requests.post(f"{BASE_URL}/apiuser", headers=headers, json=body)
if response.status_code == 201:
    key_response = requests.post(f"{BASE_URL}/apiuser/{api_user_id}/apikey", headers=headers)
    if key_response.status_code == 201:
        api_secret = key_response.json().get("apiKey")
        print(f"MTN_API_SECRET={api_secret}")
    else:
        print(f"Error getting secret key: {key_response.text}")
else:
    print(f"Error creating user: {response.text}")
