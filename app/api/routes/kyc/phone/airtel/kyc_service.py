import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class AirtelKycService:
    def __init__(self):
        self.environment = "sandbox"
        
    async def get_basic_user_info(self, phone_number: str) -> Optional[Dict]:
        """
        Fetch First Name and Last Name of the phone number owner from Airtel API.
        This is a mock implementation until the official Airtel API credentials are provided.
        """
        try:
            clean_phone = phone_number.replace("+", "")
            logger.info(f"Mocking Airtel KYC data for {clean_phone}")
            
            # Simulated successful Airtel API response format
            return {
                "first_name": "Airtel",
                "last_name": "User",
                "status": "active"
            }
        except Exception as e:
            logger.error(f"Exception during Airtel KYC fetch for {phone_number}: {str(e)}")
            return None
