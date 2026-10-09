from fastapi import APIRouter, HTTPException, status, Request

router = APIRouter()

@router.post("/delivery-report", status_code=status.HTTP_200_OK)
async def sms_delivery_report(request: Request):
    try:
        # Africa's Talking sends delivery reports as Form Data
        form_data = await request.form()
        print("\n" + "=" * 40)
        print("🔔 AFRICA'S TALKING DELIVERY REPORT 🔔")
        print("=" * 40)
        for key, value in form_data.items():
            print(f"{key}: {value}")
        print("=" * 40 + "\n")
        return {"status": "success"}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid form data."
        )
