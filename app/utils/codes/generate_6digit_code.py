import random

def generate_6digit_code() -> str:
    """Generates a random 6-digit numeric OTP code."""
    return str(random.randint(100000, 999999))
