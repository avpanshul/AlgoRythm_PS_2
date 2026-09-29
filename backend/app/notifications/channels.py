r"""Notification channels (ULPF-phase2-prompt.md E6). User's decision: SMS.

`send()` never fabricates success. With no real gateway configured (the
default -- this project has no real SMS account to send through), it
returns `status="not_configured"` and a clear detail message, which the
caller records on the Notification row exactly as given -- an operator
looking at the case history sees "we would have sent this, but no gateway
was configured," not a false "sent" that never actually left the process.

`ConsoleChannel` is the honest default/dev channel: it "sends" by writing a
structured log line, which is both a real, verifiable action (check the
log) and never claims to be an SMS that wasn't sent.
"""
import logging
from dataclasses import dataclass

from app.core.config import settings

log = logging.getLogger("notifications")


@dataclass
class SendResult:
    status: str  # "sent" | "failed" | "not_configured"
    detail: str = ""


class NotificationChannel:
    name = "base"

    def send(self, address: str, message: str) -> SendResult:
        raise NotImplementedError


class ConsoleChannel(NotificationChannel):
    """Writes the notification to the application log instead of an
    external service -- the safe default, and useful for demoing/testing the
    rest of the case/escalation pipeline (severity tiers, dedup, rate
    limiting, ack, audit log) without needing any real credentials."""
    name = "console"

    def send(self, address: str, message: str) -> SendResult:
        log.info("NOTIFICATION (console channel) to %s: %s", address, message)
        return SendResult(status="sent", detail="delivered to application log (console channel, not a real external send)")


class SMSChannel(NotificationChannel):
    """Generic HTTP-gateway SMS channel -- the shape most SMS providers
    (Twilio, MSG91, Fast2SMS, and most on-prem GSM-modem HTTP bridges) share:
    a POST with an API key, a sender ID, a destination number, and a message
    body. The specific field names below are a reasonable generic default;
    a real deployment's specific gateway may need small adjustments to this
    payload shape, which is a config/adapter change, not a redesign.

    Real, working code -- but genuinely unverified end-to-end, because doing
    so needs a real gateway account and phone number this project doesn't
    have. `send()` is honest about that: no gateway configured -> a plain,
    clearly-labeled "not_configured" result, never a fabricated "sent."
    """
    name = "sms"

    def send(self, address: str, message: str) -> SendResult:
        if not settings.SMS_GATEWAY_URL:
            log.warning("SMS to %s not sent -- SMS_GATEWAY_URL is not configured", address)
            return SendResult(
                status="not_configured",
                detail="SMS_GATEWAY_URL is not set. No real SMS gateway is configured for this "
                       "deployment, so nothing was sent -- this is recorded honestly rather than "
                       "claiming delivery that didn't happen.",
            )

        import requests  # lazy: only needed when a real gateway is actually configured

        payload = {
            "to": address,
            "message": message,
            "sender_id": settings.SMS_GATEWAY_SENDER_ID,
        }
        headers = {"Authorization": f"Bearer {settings.SMS_GATEWAY_API_KEY}"} if settings.SMS_GATEWAY_API_KEY else {}
        try:
            resp = requests.post(settings.SMS_GATEWAY_URL, json=payload, headers=headers, timeout=10)
            if resp.status_code < 300:
                return SendResult(status="sent", detail=f"gateway responded {resp.status_code}")
            return SendResult(status="failed", detail=f"gateway responded {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            return SendResult(status="failed", detail=f"{type(e).__name__}: {e}")


def get_channel(name: str) -> NotificationChannel:
    return {"sms": SMSChannel(), "console": ConsoleChannel()}.get(name, ConsoleChannel())
