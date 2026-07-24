import hashlib
import hmac

from fastapi import Header, HTTPException, status

from .config import get_settings


async def verify_internal_secret(
    x_internal_secret: str | None = Header(default=None),
) -> None:
    expected = get_settings().internal_sync_secret
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal sync is not configured",
        )
    supplied_hash = hashlib.sha256((x_internal_secret or "").encode()).digest()
    expected_hash = hashlib.sha256(expected.encode()).digest()
    if not hmac.compare_digest(supplied_hash, expected_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid secret")
