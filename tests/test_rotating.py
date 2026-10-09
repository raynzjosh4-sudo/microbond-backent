import requests
from sqlmodel import Session, select
from app.core.database import engine
from app.models.user.user import User
import time

def setup_test_user():
    phone = "+256770000000"
    with Session(engine) as session:
        user = session.exec(select(User).where(User.phone_number == phone)).first()
        if not user:
            user = User(
                phone_number=phone,
                full_name="Test Admin",
                kyc_tier=2,
                trust_score=85,
                is_phone_verified=True,
                is_dependent_account=False
            )
            session.add(user)
        else:
            user.kyc_tier = 2
            user.trust_score = 85
            user.is_dependent_account = False
            session.add(user)
        session.commit()
    return phone

def test_create_rotating():
    phone = setup_test_user()
    
    url = "http://127.0.0.1:8000/api/v1/groups/rotating/create"
    
    payload = {
        "name": "Weekly Hustlers ROSCA",
        "description": "Strict 10k weekly savings",
        "group_image_url": "https://example.com/image.png",
        "type": "MERRY_GO_ROUND",
        "payment_mode": "OBLIGATION",
        "visibility": "PRIVATE",
        "currency": "UGX",
        "created_by_phone": phone,
        
        "contribution_amount": 10000.0,
        "maximum_member_capacity": 10,
        "payouts_per_cycle": 1,
        "collection_days_interval": 7,
        "group_start_time": "2026-11-01T00:00:00Z",
        "payout_order_strategy": "Randomized by App",
        
        "minimum_kyc_tier": 2,
        "require_guarantor": True,
        "guarantor_default_action": "Charge guarantor after 48h",
        "allow_partial_payments": False,
        "allow_advance_deposits": True,
        "enforce_payout_holds": True
    }
    
    print(f"Sending POST to {url}")
    print("Payload:", payload)
    
    response = requests.post(url, json=payload)
    print("\nStatus Code:", response.status_code)
    try:
        print("Response:", response.json())
    except:
        print("Response:", response.text)

if __name__ == "__main__":
    test_create_rotating()
