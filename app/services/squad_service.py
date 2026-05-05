"""
SquadMind – Squad API Integration Service
Wraps all HTTP calls to the Squad (HabariPay) API.
Handles auth, pagination, error normalisation, and retry logic.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.logging import get_logger
from app.models.user import User

log = get_logger(__name__)

SQUAD_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class SquadAPIError(Exception):
    def __init__(self, message: str, status_code: int = 500, raw: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.raw = raw


class SquadService:
    """
    Async HTTP client for the Squad API.
    Instantiate per-request with the user's credentials.
    """

    def __init__(self, user: User) -> None:
        if not user.has_squad_credentials:
            raise SquadAPIError("User has no Squad API credentials configured", 422)
        self.secret_key = user.squad_secret_key
        self.public_key = user.squad_public_key
        self.base_url = settings.SQUAD_BASE_URL
        self.user = user

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make an authenticated GET request to Squad API."""
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=SQUAD_TIMEOUT) as client:
            try:
                response = await client.get(url, headers=self._headers(), params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                log.error(
                    "squad_api_http_error",
                    status=e.response.status_code,
                    url=url,
                    body=e.response.text[:500],
                )
                raise SquadAPIError(
                    f"Squad API error: {e.response.status_code}",
                    status_code=e.response.status_code,
                    raw=e.response.text,
                )

    async def get_transactions(
        self,
        page: int = 1,
        per_page: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Fetch paginated transaction history from Squad API.
        Docs: https://squadinc.gitbook.io/squad-api-documentation
        """
        params: Dict[str, Any] = {
            "page": page,
            "perPage": per_page,
        }
        if start_date:
            params["startDate"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            params["endDate"] = end_date.strftime("%Y-%m-%d")

        log.info("squad_fetch_transactions", user_id=str(self.user.id), page=page)
        return await self._get("/transaction/query", params=params)

    async def get_all_transactions(
        self,
        lookback_days: int = 90,
    ) -> List[Dict[str, Any]]:
        """
        Paginate through ALL transactions for the lookback window.
        Handles rate limiting automatically.
        """
        end_date = datetime.now(tz=timezone.utc)
        start_date = end_date - timedelta(days=lookback_days)

        all_transactions: List[Dict[str, Any]] = []
        page = 1

        while True:
            try:
                response = await self.get_transactions(
                    page=page,
                    per_page=100,
                    start_date=start_date,
                    end_date=end_date,
                )

                data = response.get("data", {})
                transactions = data.get("transactions", [])

                if not transactions:
                    break

                all_transactions.extend(transactions)
                log.info(
                    "squad_transactions_fetched",
                    page=page,
                    count=len(transactions),
                    total_so_far=len(all_transactions),
                )

                # Check if there are more pages
                total_pages = data.get("totalPages", 1)
                if page >= total_pages:
                    break

                page += 1
                await asyncio.sleep(0.2)  # be polite to the API

            except SquadAPIError as e:
                log.error("squad_pagination_error", page=page, error=str(e))
                break

        return all_transactions

    async def get_transaction_by_ref(self, transaction_ref: str) -> Optional[Dict[str, Any]]:
        """Fetch a single transaction by its reference."""
        try:
            response = await self._get(f"/transaction/verify/{transaction_ref}")
            return response.get("data")
        except SquadAPIError:
            return None

    async def verify_webhook(self, payload: str, signature: str) -> bool:
        """
        Verify Squad webhook HMAC signature.
        Called in the webhook endpoint to authenticate incoming events.
        """
        import hashlib
        import hmac

        expected = hmac.new(
            settings.SQUAD_WEBHOOK_SECRET.encode(),
            payload.encode(),
            hashlib.sha512,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)


# ── Transaction Normaliser ─────────────────────────────────────────────────────
def normalise_squad_transaction(raw: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Convert Squad API raw transaction payload into our normalised Transaction model fields.
    This is the translation layer between Squad's schema and ours.
    """
    from uuid import UUID

    amount_kobo = raw.get("transaction_amount", 0) or 0
    amount_ngn = Decimal(str(amount_kobo)) / 100   # Squad sends amounts in kobo

    # Determine transaction type from Squad's transaction_type field
    tx_type_map = {
        "debit": "debit",
        "credit": "credit",
        "transfer": "transfer",
        "payment": "payment",
    }
    raw_type = (raw.get("transaction_type") or "").lower()
    tx_type = tx_type_map.get(raw_type, "credit")  # default to credit

    # Parse transaction date
    date_str = raw.get("transaction_date") or raw.get("created_at") or ""
    try:
        tx_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        tx_date = datetime.now(tz=timezone.utc)

    return {
        "user_id": UUID(user_id),
        "squad_transaction_ref": raw.get("transaction_ref"),
        "squad_merchant_ref": raw.get("merchant_ref"),
        "amount": amount_ngn,
        "currency": raw.get("currency_id", "NGN"),
        "transaction_type": tx_type,
        "status": (raw.get("transaction_status") or "success").lower(),
        "customer_name": raw.get("customer_name") or raw.get("meta", {}).get("name"),
        "customer_email": raw.get("email"),
        "customer_phone": raw.get("meta", {}).get("phone"),
        "customer_id": raw.get("meta", {}).get("customer_id") or raw.get("email"),
        "payment_channel": raw.get("payment_gateway", "").lower() or None,
        "narration": raw.get("narration") or raw.get("meta", {}).get("narration"),
        "meta": raw,
        "transaction_date": tx_date,
    }
