"""
Cryptographic HMAC signature verification for Razorpay payments and webhooks.

Uses constant-time comparison (hmac.compare_digest) to prevent timing attacks.
Never logs secrets or sensitive signature payloads.
"""

import hashlib
import hmac
from typing import Union


def verify_payment_signature(
    order_id: str,
    payment_id: str,
    signature: str,
    secret: str,
) -> bool:
    """
    Verify a Razorpay payment signature after customer checkout.

    The expected signature is the HMAC-SHA256 of `order_id|payment_id`
    using the merchant's key_secret.
    """
    if not order_id or not payment_id or not signature or not secret:
        return False

    msg = f"{order_id}|{payment_id}".encode("utf-8")
    key = secret.encode("utf-8")
    expected_signature = hmac.new(key, msg, hashlib.sha256).hexdigest()

    return hmac.compare_digest(expected_signature, signature)


def verify_webhook_signature(
    raw_body: Union[bytes, str],
    signature: str,
    secret: str,
) -> bool:
    """
    Verify the inbound webhook signature sent in the X-Razorpay-Signature header.

    The expected signature is the HMAC-SHA256 of the raw unparsed request body
    using the merchant's webhook_secret.
    """
    if raw_body is None or not signature or not secret:
        return False

    body_bytes = raw_body.encode("utf-8") if isinstance(raw_body, str) else raw_body
    key = secret.encode("utf-8")
    expected_signature = hmac.new(key, body_bytes, hashlib.sha256).hexdigest()

    return hmac.compare_digest(expected_signature, signature)


def create_hmac_sha256_signature(
    raw_body: Union[bytes, str],
    secret: str,
) -> str:
    """
    Generate an HMAC-SHA256 hex digest signature for testing or simulation.
    """
    body_bytes = raw_body.encode("utf-8") if isinstance(raw_body, str) else raw_body
    key = secret.encode("utf-8")
    return hmac.new(key, body_bytes, hashlib.sha256).hexdigest()

