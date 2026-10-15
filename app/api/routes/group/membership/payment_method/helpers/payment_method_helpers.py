

def mask_account_number(number: str) -> str:
    if len(number) < 4:
        return "****"
    return f"**** {number[-4:]}"
