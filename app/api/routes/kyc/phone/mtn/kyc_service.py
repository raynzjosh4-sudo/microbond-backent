import os
import httpx
import base64
import logging
from typing import Optional, Dict
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class MTNKycService:
    def __init__(self):
        self.api_user = os.getenv("MTN_API_USER")
        self.api_secret = os.getenv("MTN_API_SECRET")
        self.subscription_key = os.getenv("MTN_SUBSCRIPTION_KEY")
        # Ensure we use the collection product base URL for basicuserinfo
        self.base_url = "https://sandbox.momodeveloper.mtn.com/collection"
        self.environment = "sandbox"
        
    async def _get_access_token(self) -> str:
        """Generates an OAuth bearer token using API User and Secret."""
        auth_string = f"{self.api_user}:{self.api_secret}"
        encoded_auth = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
        
        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Ocp-Apim-Subscription-Key": self.subscription_key
        }
        
        url = f"{self.base_url}/token/"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("access_token")

    async def get_basic_user_info(self, phone_number: str) -> Optional[Dict]:
        """
        Fetch First Name and Last Name of the phone number owner.
        Designed to be run as a FastAPI BackgroundTask.
        """
        try:
            # 1. Fetch access token
            token = await self._get_access_token()
            
            # 2. Prepare headers for KYC request
            headers = {
                "Authorization": f"Bearer {token}",
                "X-Target-Environment": self.environment,
                "Ocp-Apim-Subscription-Key": self.subscription_key
            }
            
            # 3. Clean phone number (MTN usually expects MSISDN e.g., 256771234567 without the '+')
            clean_phone = phone_number.replace("+", "")
            if clean_phone.startswith("0"):
                # Assuming Uganda prefix 256 for local numbers starting with 0
                clean_phone = f"256{clean_phone[1:]}"
            
            url = f"{self.base_url}/v1_0/accountholder/msisdn/{clean_phone}/basicuserinfo"
            
            # 4. Make request to basicuserinfo endpoint
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Successfully fetched KYC data for {clean_phone}")
                    return data
                else:
                    logger.error(
                        f"Failed to fetch KYC for {clean_phone}. "
                        f"Status: {response.status_code}, Body: {response.text}"
                    )
                    return None
                    
        except Exception as e:
            logger.error(f"Exception during MTN KYC fetch for {phone_number}: {str(e)}")
            return None
