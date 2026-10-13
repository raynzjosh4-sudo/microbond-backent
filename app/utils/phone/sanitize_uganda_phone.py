def sanitize_uganda_phone(phone: str) -> str:
    """
    Formats local Ugandan inputs (0771234567, 0701234567, 25677...)
    into standard E.164 (+256771234567).
    """
    clean = phone.strip().replace(" ", "").replace("-", "")
    if clean.startswith("07"):
        return "+256" + clean[1:]
    if clean.startswith("256"):
        return "+" + clean
    if not clean.startswith("+"):
        return "+" + clean
    return clean
