"""Optional, server-only email transports with safe failure reporting.

An accepted message is not proof of delivery to a mailbox. No transport is
retried automatically: after a timeout the provider might already have sent it.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage

import httpx

from app.core.config import Settings

logger = logging.getLogger("uvicorn.error")
RESEND_SEND_URL = "https://api.resend.com/emails"


def send_email(*, recipient: str, subject: str, text_body: str, config: Settings) -> bool:
    """Return whether the configured provider accepted one message.

    Only fixed reason codes, HTTP status codes and exception types reach logs;
    never record recipient addresses, credentials, links or provider bodies.
    """
    if config.email_provider == "disabled":
        logger.warning("email_delivery_skipped provider=disabled reason=disabled")
        return False
    if config.email_provider == "resend":
        if not (config.resend_api_key and config.email_from):
            logger.warning("email_delivery_skipped provider=resend reason=missing_configuration")
            return False
        return _send_resend(recipient, subject, text_body, config)
    if not all([config.smtp_host, config.smtp_user, config.smtp_password, config.smtp_from]):
        logger.warning("email_delivery_skipped provider=smtp reason=missing_configuration")
        return False
    return _send_smtp(recipient, subject, text_body, config)


def _send_resend(recipient: str, subject: str, text_body: str, config: Settings) -> bool:
    try:
        # Explicitly disable transport retries and redirects so an uncertain
        # POST is never repeated or forwarded, together with its reset token.
        with httpx.Client(
            transport=httpx.HTTPTransport(retries=0, trust_env=False),
            timeout=httpx.Timeout(config.email_timeout_seconds),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = client.post(
                RESEND_SEND_URL,
                headers={"Authorization": f"Bearer {config.resend_api_key.get_secret_value()}"},
                json={
                    "from": str(config.email_from),
                    "to": [recipient],
                    "subject": subject,
                    "text": text_body,
                },
            )
    except (httpx.HTTPError, OSError) as exc:
        logger.warning(
            "email_delivery_failed provider=resend reason=transport_error error_type=%s",
            type(exc).__name__,
        )
        return False
    if not response.is_success:
        logger.warning(
            "email_delivery_failed provider=resend reason=provider_rejected status_code=%s",
            response.status_code,
        )
        return False
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if not isinstance(payload, dict) or not isinstance(payload.get("id"), str) or not payload["id"].strip():
        logger.warning("email_delivery_failed provider=resend reason=invalid_response")
        return False
    logger.info("email_delivery_accepted provider=resend")
    return True


def _send_smtp(recipient: str, subject: str, text_body: str, config: Settings) -> bool:
    try:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = config.smtp_from
        message["To"] = recipient
        message.set_content(text_body)
        smtp_class = smtplib.SMTP_SSL if config.smtp_use_ssl else smtplib.SMTP
        kwargs = {"timeout": config.smtp_timeout_seconds}
        if config.smtp_use_ssl:
            kwargs["context"] = ssl.create_default_context()
        with smtp_class(config.smtp_host, config.smtp_port, **kwargs) as smtp:
            if config.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            smtp.login(config.smtp_user, config.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        logger.warning(
            "email_delivery_failed provider=smtp reason=transport_error error_type=%s",
            type(exc).__name__,
        )
        return False
    logger.info("email_delivery_accepted provider=smtp")
    return True
