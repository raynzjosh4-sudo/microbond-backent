import random

def generate_6digit_code() -> str:
    return str(random.randint(100000, 999999))
