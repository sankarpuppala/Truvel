"""Send an email, or say plainly that it could not be sent.

Truvel has no paid mail service (CLAUDE.md: zero budget), so delivery uses any
ordinary SMTP account you already have, set in the environment:

    TRUVEL_SMTP_HOST   TRUVEL_SMTP_PORT (587)   TRUVEL_SMTP_USER
    TRUVEL_SMTP_PASSWORD   TRUVEL_SMTP_FROM

With no SMTP host set (the default on a laptop) nothing is sent; the message is
written to the server log instead so you can follow the link while developing.
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

log = logging.getLogger("truvel.mail")


def configured() -> bool:
    return bool(os.environ.get("TRUVEL_SMTP_HOST"))


def send(to: str, subject: str, body: str) -> bool:
    """Returns True if handed to an SMTP server, False if only logged."""
    if not configured():
        log.warning("Email not configured; would have sent to %s: %s\n%s", to, subject, body)
        return False

    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    message["From"] = os.environ.get("TRUVEL_SMTP_FROM") or os.environ.get("TRUVEL_SMTP_USER", "")
    message.set_content(body)

    host = os.environ["TRUVEL_SMTP_HOST"]
    port = int(os.environ.get("TRUVEL_SMTP_PORT", "587"))
    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls()
            user = os.environ.get("TRUVEL_SMTP_USER")
            if user:
                smtp.login(user, os.environ.get("TRUVEL_SMTP_PASSWORD", ""))
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        log.exception("Could not send email to %s", to)
        return False
    return True
