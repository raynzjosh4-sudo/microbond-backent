from fastapi.testclient import TestClient
from app.main import app

def run_test():
    client = TestClient(app)
    payload = {
        "name": "Weekly Hustlers ROSCA",
        "description": "Strict 10k weekly savings",
        "group_image_url": "https://example.com/image.png",
        "type": "MERRY_GO_ROUND",
        "payment_mode": "OBLIGATION",
        "visibility": "PRIVATE",
        "currency": "UGX",
        "created_by_phone": "+256770000000",
        
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
    
    response = client.post("/api/v1/groups/rotating/create", json=payload)
    print("Status code:", response.status_code)
    print("Response JSON:", response.json())

if __name__ == "__main__":
    run_test()
