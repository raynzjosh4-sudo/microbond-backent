def mask_phone_number(phone: str) -> str:
    if not phone or len(phone) < 7:
        return "****"
    return phone[:6] + "****" + phone[-2:]
