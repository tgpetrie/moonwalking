"""Alerting helpers (webhook + email) for operational events.

Lightweight: avoids external libs; email via smtplib if configured.
"""
from __future__ import annotations
import os, time, json, logging, smtplib, ssl
from email.message import EmailMessage
from typing import Optional, Iterable, Dict, Any
import threading
import urllib.request

class AlertNotifier:
    def __init__(self,
                 enabled: bool,
                 channels: set[str],
                 webhook_url: Optional[str],
                 email_to: list[str],
                 email_from: Optional[str],
                 smtp_host: Optional[str],
                 smtp_port: int,
                 smtp_user: Optional[str],
                 smtp_pass: Optional[str],
                 cooldown_sec: int):
        self.enabled = enabled
        self.channels = channels
        self.webhook_url = webhook_url
        self.email_to = email_to
        self.email_from = email_from
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
        self.cooldown_sec = cooldown_sec
        self._last_sent: Dict[str,float] = {}
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls) -> 'AlertNotifier':
        enabled = os.environ.get('ALERT_ENABLED','0') == '1'
        channels = {c.strip() for c in os.environ.get('ALERT_CHANNELS','').split(',') if c.strip()}
        webhook = os.environ.get('ALERT_WEBHOOK_URL')
        email_to = [e.strip() for e in os.environ.get('ALERT_EMAIL_TO','').split(',') if e.strip()]
        return cls(
            enabled=enabled,
            channels=channels,
            webhook_url=webhook,
            email_to=email_to,
            email_from=os.environ.get('ALERT_EMAIL_FROM'),
            smtp_host=os.environ.get('ALERT_EMAIL_SMTP_HOST'),
            smtp_port=int(os.environ.get('ALERT_EMAIL_SMTP_PORT','587')),
            smtp_user=os.environ.get('ALERT_EMAIL_SMTP_USER'),
            smtp_pass=os.environ.get('ALERT_EMAIL_SMTP_PASS'),
            cooldown_sec=int(os.environ.get('ALERT_COOLDOWN_SEC','300'))
        )

    def _should_send(self, event: str) -> bool:
        now = time.time()
        with self._lock:
            last = self._last_sent.get(event, 0)
            if (now - last) < self.cooldown_sec:
                return False
            self._last_sent[event] = now
            return True

    def send(self, event: str, details: Dict[str, Any]):
        if not self.enabled:
            return
        if not self._should_send(event):
            return
        payload = {
            'event': event,
            'at': int(time.time()),
            'details': details or {}
        }
        if 'webhook' in self.channels and self.webhook_url:
            try:
                req = urllib.request.Request(self.webhook_url, method='POST')
                data = json.dumps(payload).encode('utf-8')
                req.add_header('Content-Type','application/json')
                urllib.request.urlopen(req, data=data, timeout=5)  # nosec - controlled by config
            except Exception as e:  # pragma: no cover - network issues
                logging.warning('alerting.webhook_failed', extra={'event':'alert_webhook_failed','error':str(e)})
        if 'email' in self.channels and self.email_to and self.email_from and self.smtp_host:
            try:
                msg = EmailMessage()
                msg['Subject'] = f"[Moonwalking Alert] {event}"
                msg['From'] = self.email_from
                msg['To'] = ', '.join(self.email_to)
                msg.set_content(json.dumps(payload, indent=2))
                context = ssl.create_default_context()
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as s:
                    try:
                        s.starttls(context=context)
                    except Exception:
                        pass
                    if self.smtp_user and self.smtp_pass:
                        try:
                            s.login(self.smtp_user, self.smtp_pass)
                        except Exception:
                            logging.warning('alerting.smtp_login_failed')
                    s.send_message(msg)
            except Exception as e:  # pragma: no cover
                logging.warning('alerting.email_failed', extra={'event':'alert_email_failed','error':str(e)})

__all__ = ['AlertNotifier']