"""Transactional email sending for account flows.

Reuses the SMTP configuration already used by alert delivery (``MW_SMTP_*``)
so operators configure one mail server, not two. Deliberately stdlib-only:
no vendor SDK is introduced.
"""

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage


class MailNotConfigured(RuntimeError):
    """Raised when no SMTP server is configured for this deployment."""


class MailSendError(RuntimeError):
    """Raised when the SMTP server refused or dropped the message."""


def _as_int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(str(os.getenv(name) or default).strip())
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def is_configured() -> bool:
    """True when enough SMTP settings exist to attempt a send."""
    host = str(os.getenv("MW_SMTP_HOST") or "").strip()
    sender = str(
        os.getenv("MW_AUTH_EMAIL_FROM")
        or os.getenv("MW_ALERT_EMAIL_FROM")
        or os.getenv("MW_SMTP_USERNAME")
        or ""
    ).strip()
    return bool(host and sender)


def send_email(*, to: str, subject: str, body: str) -> None:
    """Send one plain-text message.

    Raises:
        MailNotConfigured: no SMTP host/sender configured.
        MailSendError: the server rejected the message.
    """
    host = str(os.getenv("MW_SMTP_HOST") or "").strip()
    port = _as_int("MW_SMTP_PORT", 587, 1, 65535)
    username = str(os.getenv("MW_SMTP_USERNAME") or "").strip()
    password = str(os.getenv("MW_SMTP_PASSWORD") or "")
    sender = str(
        os.getenv("MW_AUTH_EMAIL_FROM")
        or os.getenv("MW_ALERT_EMAIL_FROM")
        or username
        or ""
    ).strip()
    recipient = str(to or "").strip()

    if not host or not sender:
        raise MailNotConfigured("smtp_not_configured")
    if not recipient:
        raise MailSendError("missing_recipient")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(body)

    timeout = _as_int("MW_NOTIFY_TIMEOUT_SECONDS", 8, 2, 30)
    try:
        if _env_bool("MW_SMTP_SSL", False):
            with smtplib.SMTP_SSL(
                host, port, timeout=timeout, context=ssl.create_default_context()
            ) as client:
                if username:
                    client.login(username, password)
                client.send_message(message)
            return
        with smtplib.SMTP(host, port, timeout=timeout) as client:
            if _env_bool("MW_SMTP_STARTTLS", True):
                client.starttls(context=ssl.create_default_context())
            if username:
                client.login(username, password)
            client.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        # Never include the message body here: it carries the reset link.
        logging.warning("auth_email_send_failed: %s", type(exc).__name__)
        raise MailSendError("smtp_send_failed") from exc
