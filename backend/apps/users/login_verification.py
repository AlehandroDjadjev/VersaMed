import math
import secrets
import time
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.core.mail import send_mail


User = get_user_model()
LOGIN_CHALLENGE_PREFIX = "users:login_challenge:"


class LoginVerificationError(Exception):
    def __init__(self, message, field_name="code"):
        super().__init__(message)
        self.field_name = field_name


@dataclass
class LoginChallenge:
    challenge_id: str
    expires_in: int
    dev_code: str | None = None


def _challenge_key(challenge_id):
    return f"{LOGIN_CHALLENGE_PREFIX}{challenge_id}"


def _code_ttl_seconds():
    return getattr(settings, "LOGIN_VERIFICATION_CODE_TTL_SECONDS", 600)


def _max_attempts():
    return getattr(settings, "LOGIN_VERIFICATION_MAX_ATTEMPTS", 5)


def _remaining_timeout(challenge):
    return max(1, math.ceil(challenge["expires_at"] - time.time()))


def _verification_message(code, expires_in):
    minutes = max(1, math.ceil(expires_in / 60))
    return (
        "Use this VersaMed verification code to complete your sign in: "
        f"{code}\n\n"
        f"This code expires in {minutes} minutes."
    )


def create_login_challenge(user):
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge_id = secrets.token_urlsafe(24)
    expires_in = _code_ttl_seconds()

    cache.set(
        _challenge_key(challenge_id),
        {
            "user_id": user.pk,
            "code_hash": make_password(code),
            "expires_at": time.time() + expires_in,
            "attempts_left": _max_attempts(),
        },
        timeout=expires_in,
    )

    send_mail(
        subject="Your VersaMed verification code",
        message=_verification_message(code, expires_in),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@versamed.local"),
        recipient_list=[user.email],
        fail_silently=False,
    )

    return LoginChallenge(
        challenge_id=challenge_id,
        expires_in=expires_in,
        dev_code=code if settings.DEBUG else None,
    )


def verify_login_challenge(challenge_id, code):
    challenge = cache.get(_challenge_key(challenge_id))
    if not challenge:
        raise LoginVerificationError(
            "This verification code has expired. Please sign in again."
        )

    if not check_password(code, challenge["code_hash"]):
        attempts_left = challenge["attempts_left"] - 1
        if attempts_left <= 0:
            cache.delete(_challenge_key(challenge_id))
            raise LoginVerificationError(
                "Too many incorrect attempts. Please sign in again."
            )

        challenge["attempts_left"] = attempts_left
        cache.set(
            _challenge_key(challenge_id),
            challenge,
            timeout=_remaining_timeout(challenge),
        )
        raise LoginVerificationError(
            f"That code is not correct. {attempts_left} attempts remaining."
        )

    user = User.objects.filter(pk=challenge["user_id"]).first()
    cache.delete(_challenge_key(challenge_id))

    if user is None or not user.is_active:
        raise LoginVerificationError("This account is inactive.", field_name="email")

    return user
