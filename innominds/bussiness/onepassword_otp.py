import time
import pyotp
from config.read_config import otp_secrets_cred


class OTPGenerator:
    def __init__(self, provider: str, user: str):
        self.otp_secret = otp_secrets_cred[provider][user]['secret_key']
        self.totp = pyotp.TOTP(self.otp_secret)

    def get_otp_with_remaining_time(self) -> tuple[str, int]:
        """
        Returns:
            (otp, remaining_seconds)
        """
        otp = self.totp.now()
        remaining_time = 30 - int(time.time()) % 30
        return otp, remaining_time

    def get_fresh_otp(self, min_validity: int = 10) -> str:
        """
        Ensures OTP has at least `min_validity` seconds left
        """
        while True:
            otp, remaining = self.get_otp_with_remaining_time()
            if remaining >= min_validity:
                return otp
            time.sleep(1)


# otp_gen = OTPGenerator("Entra_ID", "testuser1")

# otp, remaining = otp_gen.get_otp_with_remaining_time()

# print("Current OTP:", otp)
# print("OTP valid for:", remaining, "seconds")
# otp = otp_gen.get_fresh_otp()
# print("Fresh OTP with sufficient validity:", otp)