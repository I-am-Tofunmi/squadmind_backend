"""
SquadMind – Alert Service
Dispatches alerts via WhatsApp (Twilio), SMS, and Email (SendGrid).
Persists all sent alerts to the database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.alert import Alert
from app.models.user import User

log = get_logger(__name__)


class AlertService:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def send_alert(
        self,
        user: User,
        alert_type: str,
        channel: str,
        title: str,
        message: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Dispatch an alert via the specified channel and persist it.
        Returns the result dict.
        """
        # Determine recipient
        recipient = self._get_recipient(user, channel)
        if not recipient:
            return {
                "success": False,
                "error": f"No {channel} contact configured for this user.",
                "channel": channel,
            }

        # Create DB record first
        alert = Alert(
            user_id=user.id,
            alert_type=alert_type,
            channel=channel,
            title=title,
            message=message,
            recipient=recipient,
            status="pending",
            meta=meta or {},
        )
        self.db.add(alert)
        await self.db.flush()

        # Dispatch
        try:
            if channel == "whatsapp":
                provider_response = await self._send_whatsapp(recipient, title, message)
            elif channel == "sms":
                provider_response = await self._send_sms(recipient, message)
            elif channel == "email":
                provider_response = await self._send_email(recipient, title, message, user.business_name)
            else:
                raise ValueError(f"Unknown alert channel: {channel}")

            alert.status = "sent"
            alert.sent_at = datetime.now(tz=timezone.utc)
            alert.meta = {**(meta or {}), "provider_response": provider_response}

            log.info(
                "alert_sent",
                user_id=str(user.id),
                channel=channel,
                alert_type=alert_type,
                alert_id=str(alert.id),
            )

            return {
                "success": True,
                "alert_id": str(alert.id),
                "channel": channel,
                "recipient": recipient,
                "status": "sent",
            }

        except Exception as e:
            alert.status = "failed"
            alert.error_message = str(e)

            log.error(
                "alert_send_failed",
                user_id=str(user.id),
                channel=channel,
                error=str(e),
            )

            return {
                "success": False,
                "alert_id": str(alert.id),
                "channel": channel,
                "error": str(e),
                "status": "failed",
            }

    def _get_recipient(self, user: User, channel: str) -> Optional[str]:
        """Resolve the recipient address for a channel."""
        if channel == "whatsapp":
            phone = user.alert_phone or user.phone
            if phone and user.whatsapp_enabled:
                # Normalise to E.164 with whatsapp: prefix
                clean = phone.replace(" ", "").replace("-", "")
                if not clean.startswith("+"):
                    clean = "+234" + clean.lstrip("0")
                return f"whatsapp:{clean}"
        elif channel == "sms":
            phone = user.alert_phone or user.phone
            if phone and user.sms_enabled:
                clean = phone.replace(" ", "").replace("-", "")
                if not clean.startswith("+"):
                    clean = "+234" + clean.lstrip("0")
                return clean
        elif channel == "email":
            if user.email_alerts_enabled:
                return user.email
        return None

    async def _send_whatsapp(self, to: str, title: str, message: str) -> Dict:
        """Send WhatsApp message via Twilio."""
        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
            log.warning("twilio_not_configured")
            return {"mock": True, "to": to}

        try:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

            body = f"🤖 *SquadMind Alert*\n\n*{title}*\n\n{message}\n\n_SquadMind AI CFO_"
            msg = client.messages.create(
                from_=settings.TWILIO_WHATSAPP_NUMBER,
                to=to,
                body=body,
            )
            return {"sid": msg.sid, "status": msg.status}
        except Exception as e:
            log.error("whatsapp_send_error", error=str(e))
            raise

    async def _send_sms(self, to: str, message: str) -> Dict:
        """Send SMS via Twilio."""
        if not settings.TWILIO_ACCOUNT_SID:
            return {"mock": True, "to": to}

        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            from_=settings.TWILIO_SMS_NUMBER,
            to=to,
            body=f"SquadMind: {message}",
        )
        return {"sid": msg.sid, "status": msg.status}

    async def _send_email(
        self, to: str, subject: str, message: str, business_name: str
    ) -> Dict:
        """Send email via SendGrid."""
        if not settings.SENDGRID_API_KEY:
            log.warning("sendgrid_not_configured")
            return {"mock": True, "to": to}

        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail

            sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
              <h2 style="color: #1a56db;">🤖 SquadMind AI CFO</h2>
              <h3>{subject}</h3>
              <p style="color: #374151;">{message}</p>
              <hr/>
              <p style="font-size: 12px; color: #9ca3af;">
                This alert was generated by SquadMind for {business_name}.
              </p>
            </div>
            """
            mail = Mail(
                from_email=(settings.SENDGRID_FROM_EMAIL, settings.SENDGRID_FROM_NAME),
                to_emails=to,
                subject=f"[SquadMind] {subject}",
                html_content=html_content,
            )
            response = sg.send(mail)
            return {"status_code": response.status_code}
        except Exception as e:
            log.error("email_send_error", error=str(e))
            raise


# ── Alert Trigger Helpers (called from other services) ────────────────────────

async def trigger_fraud_alert(db: AsyncSession, user: User, tx: Any, fraud_result: Dict) -> None:
    """Fire fraud alert across all enabled channels."""
    service = AlertService(db)
    msg = (
        f"🚨 Suspicious transaction detected!\n"
        f"Amount: ₦{float(tx.amount):,.2f}\n"
        f"Risk: {fraud_result['risk_level'].upper()} ({fraud_result['risk_score']:.0f}/100)\n"
        f"Flags: {', '.join(fraud_result['rules_triggered'])}"
    )

    for channel in ["whatsapp", "email"]:
        await service.send_alert(
            user=user,
            alert_type="fraud_detected",
            channel=channel,
            title="Fraud Alert — Action Required",
            message=msg,
            meta={"transaction_id": str(tx.id), "risk_score": fraud_result["risk_score"]},
        )


async def trigger_large_transaction_alert(db: AsyncSession, user: User, tx: Any) -> None:
    """Alert on large transactions above threshold."""
    service = AlertService(db)
    await service.send_alert(
        user=user,
        alert_type="large_transaction",
        channel="whatsapp",
        title="Large Transaction Alert",
        message=f"A transaction of ₦{float(tx.amount):,.2f} was received from {tx.customer_name or 'Unknown Customer'}.",
        meta={"transaction_id": str(tx.id)},
    )
