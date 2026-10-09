import asyncio
import httpx
from sqlmodel import Session
from app.core.database import engine, get_session
from app.models.user.user import User
from app.core.security import create_access_token

async def run_test():
    # 1. Ensure we have a user in the database
    with Session(engine) as session:
        user = session.query(User).first()
        if not user:
            print("Creating a dummy user for testing...")
            user = User(
                phone_number="+256701234567",
                is_phone_verified=True,
                is_profile_complete=False
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            
        print(f"Using user: ID={user.id}, Phone={user.phone_number}")
        
        # 2. Generate a valid auth token for this user
        access_token = create_access_token(data={"sub": str(user.id), "phone": user.phone_number})

    # 3. Test the Prembly NIN Verification endpoint
    # You must provide a valid Ugandan NIN format: 14 alphanumeric characters. Example: CM123456789012
    # In production, this hits the Prembly Sandbox because of your keys.
    test_payload = {
        "nin": "CM030521146GVE",
        "first_name": "SSENKINDU",
        "last_name": "EMMANUEL",
        "dob": "2003-01-24",
        "document_id": "000092896",
        "is_dependent": False
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    print("\n--- Testing Prembly NIN Verification Endpoint ---")
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30.0) as client:
        response = await client.post("/api/v1/kyc/nin/prembly/verify", json=test_payload, headers=headers)
        
        print(f"Status Code: {response.status_code}")
        print("Response Body:")
        print(response.json())

if __name__ == "__main__":
    asyncio.run(run_test())
