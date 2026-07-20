"""Optional free alert delivery channels with transition dedupe and budgets."""

from __future__ import annotations

from collections import deque
from email.message import EmailMessage
import json
import logging
import os
import smtplib
import ssl
import threading
import time
from typing import Any, Callable
from urllib.request import Request, urlopen


def _env_bool(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "1" if default else "0") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _as_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except Exception:
        value = default
    return max(minimum, min(value, maximum))


def _event_ts_ms(event: dict[str, Any]) -> int:
    for key in ("latest_transition_ts_ms", "event_ts_ms", "ts_ms"):
        try:
            value = int(float(event.get(key)))
            return value if value >= 10_000_000_000 else value * 1000
        except Exception:
            continue
    return 0


def format_delivery(event: dict[str, Any]) -> tuple[str, str]:
    symbol = str(event.get("symbol") or event.get("product_id") or "MARKET").replace(
        "-USD", ""
    )
    state = str(event.get("primary_state") or event.get("title") or "Signal")
    modifier = str(event.get("modifier") or "").strip()
    confidence = event.get("confidence")
    path = str((event.get("evidence") or {}).get("event_path") or state)
    subject = f"Moonwalkings: {symbol} {state}"
    lines = [
        f"{symbol} · {state}" + (f" · {modifier}" if modifier else ""),
        f"Confidence: {confidence if confidence is not None else 'unavailable'}",
        f"Evolution: {path}",
        f"Detections: {int(event.get('alert_count') or 0)}",
        str(event.get("message") or "Signal event updated."),
    ]
    if event.get("trade_url"):
        lines.append(str(event["trade_url"]))
    return subject, "\n".join(lines)


class AlertDeliveryDispatcher:
    """Deliver newly eligible event transitions without blocking the scan loop."""

    def __init__(self) -> None:
        self.enabled = _env_bool("MW_ALERT_NOTIFY_ENABLED", False)
        self.max_per_hour = _as_int("MW_NOTIFY_MAX_PER_HOUR", 6, 1, 120)
        self.cooldown_seconds = _as_int(
            "MW_NOTIFY_SYMBOL_COOLDOWN_SECONDS", 900, 0, 86_400
        )
        self.max_event_age_seconds = _as_int(
            "MW_NOTIFY_MAX_EVENT_AGE_SECONDS", 120, 15, 3600
        )
        self._lock = threading.Lock()
        self._running = False
        self._sent_ids: dict[str, float] = {}
        self._last_by_symbol: dict[str, tuple[float, str]] = {}
        self._sent_ring: deque[float] = deque(maxlen=500)
        self._last_error: str | None = None
        self._last_sent_at: float | None = None

    def _email_configured(self) -> bool:
        return bool(os.getenv("MW_SMTP_HOST") and os.getenv("MW_ALERT_EMAIL_TO"))

    def _telegram_configured(self) -> bool:
        return bool(
            os.getenv("MW_TELEGRAM_BOT_TOKEN") and os.getenv("MW_TELEGRAM_CHAT_ID")
        )

    def _discord_configured(self) -> bool:
        return bool(os.getenv("MW_DISCORD_WEBHOOK_URL"))

    def status(self) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            recent = [ts for ts in self._sent_ring if now - ts < 3600]
            return {
                "enabled": self.enabled,
                "channels": {
                    "email": self._email_configured(),
                    "telegram": self._telegram_configured(),
                    "discord": self._discord_configured(),
                },
                "max_per_hour": self.max_per_hour,
                "symbol_cooldown_seconds": self.cooldown_seconds,
                "sent_last_hour": len(recent),
                "last_sent_at": self._last_sent_at,
                "last_error": self._last_error,
            }

    def dispatch_async(self, events: list[dict[str, Any]]) -> bool:
        if not self.enabled or not events:
            return False
        with self._lock:
            if self._running:
                return False
            self._running = True
        thread = threading.Thread(
            target=self._run,
            args=(list(events),),
            daemon=True,
            name="mw-alert-delivery",
        )
        thread.start()
        return True

    def _run(self, events: list[dict[str, Any]]) -> None:
        try:
            self.dispatch(events)
        finally:
            with self._lock:
                self._running = False

    def dispatch(
        self, events: list[dict[str, Any]], *, now: float | None = None
    ) -> int:
        if not self.enabled:
            return 0
        now = float(now if now is not None else time.time())
        channels: list[tuple[str, Callable[[dict[str, Any]], None]]] = []
        if self._email_configured():
            channels.append(("email", self._send_email))
        if self._telegram_configured():
            channels.append(("telegram", self._send_telegram))
        if self._discord_configured():
            channels.append(("discord", self._send_discord))
        if not channels:
            return 0

        with self._lock:
            while self._sent_ring and now - self._sent_ring[0] >= 3600:
                self._sent_ring.popleft()
            if len(self._sent_ring) >= self.max_per_hour:
                return 0

        delivered = 0
        ordered = sorted(
            events, key=lambda event: int(event.get("confidence") or 0), reverse=True
        )
        for event in ordered:
            if len(self._sent_ring) >= self.max_per_hour:
                break
            event_id = str(event.get("id") or "")
            symbol = str(event.get("symbol") or event.get("product_id") or "").upper()
            state = str(event.get("primary_state") or "")
            event_age = now - (_event_ts_ms(event) / 1000.0)
            if (
                not event_id
                or not symbol
                or event_age < -30
                or event_age > self.max_event_age_seconds
            ):
                continue
            if event_id in self._sent_ids:
                continue
            last_symbol = self._last_by_symbol.get(symbol)
            is_risk_flip = (
                state == "Reversal Risk" and last_symbol and last_symbol[1] != state
            )
            if (
                last_symbol
                and (now - last_symbol[0]) < self.cooldown_seconds
                and not is_risk_flip
            ):
                continue

            successes = 0
            for channel_name, sender in channels:
                try:
                    sender(event)
                    successes += 1
                except Exception as exc:
                    logging.warning(
                        "Alert delivery channel %s failed: %s",
                        channel_name,
                        type(exc).__name__,
                    )
                    with self._lock:
                        self._last_error = f"{channel_name}:{type(exc).__name__}"
            if successes:
                delivered += 1
                with self._lock:
                    self._sent_ids[event_id] = now
                    self._last_by_symbol[symbol] = (now, state)
                    self._sent_ring.append(now)
                    self._last_sent_at = now
                    self._last_error = None
        return delivered

    def _send_email(self, event: dict[str, Any]) -> None:
        host = str(os.getenv("MW_SMTP_HOST") or "").strip()
        port = _as_int("MW_SMTP_PORT", 587, 1, 65535)
        username = str(os.getenv("MW_SMTP_USERNAME") or "").strip()
        password = str(os.getenv("MW_SMTP_PASSWORD") or "")
        sender = str(os.getenv("MW_ALERT_EMAIL_FROM") or username).strip()
        recipients = [
            item.strip()
            for item in str(os.getenv("MW_ALERT_EMAIL_TO") or "").split(",")
            if item.strip()
        ]
        if not host or not sender or not recipients:
            raise RuntimeError("smtp_not_configured")
        subject, body = format_delivery(event)
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = ", ".join(recipients)
        message.set_content(body)

        timeout = _as_int("MW_NOTIFY_TIMEOUT_SECONDS", 8, 2, 30)
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

    def _post_json(self, url: str, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        request = Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        timeout = _as_int("MW_NOTIFY_TIMEOUT_SECONDS", 8, 2, 30)
        with urlopen(
            request, timeout=timeout
        ) as response:  # nosec B310 - operator-configured webhook
            if int(getattr(response, "status", 200)) >= 400:
                raise RuntimeError("webhook_http_error")

    def _send_telegram(self, event: dict[str, Any]) -> None:
        token = str(os.getenv("MW_TELEGRAM_BOT_TOKEN") or "").strip()
        chat_id = str(os.getenv("MW_TELEGRAM_CHAT_ID") or "").strip()
        _subject, body = format_delivery(event)
        self._post_json(
            f"https://api.telegram.org/bot{token}/sendMessage",
            {"chat_id": chat_id, "text": body, "disable_web_page_preview": True},
        )

    def _send_discord(self, event: dict[str, Any]) -> None:
        url = str(os.getenv("MW_DISCORD_WEBHOOK_URL") or "").strip()
        subject, body = format_delivery(event)
        self._post_json(url, {"content": f"**{subject}**\n{body}"[:1900]})


dispatcher = AlertDeliveryDispatcher()
