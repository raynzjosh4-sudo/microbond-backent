from app.services.communication.sms.helpers.send_sms import send_sms


def send_real_otp_sms(phone_number: str, code: str) -> bool:
    message = f"Your Microbond code is: {code}. Valid for 5 minutes. Do not share it."
    return send_sms(phone_number, message)
