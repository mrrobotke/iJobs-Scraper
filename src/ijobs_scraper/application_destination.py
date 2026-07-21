"""Resolve candidate application destinations without leaking scraper provenance.

``RawListing.external_url`` identifies the page that was scraped. It is useful for
fetching, deduplication, and audit history, but it is not automatically a place where
a candidate should apply. This module derives a separate, tightly validated destination
from explicit application instructions.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, quote, unquote, urlsplit

_CONTROL_CHARACTER_RE = re.compile(r"[\x00-\x1f\x7f]")
_EMAIL_RE = re.compile(
    r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?"
    r"(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+",
    re.IGNORECASE,
)
_HTTP_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_MAILTO_URL_RE = re.compile(r"mailto:[^\s<>\"']+", re.IGNORECASE)
_BARE_DOMAIN_RE = re.compile(
    r"(?<![@\w-])"
    r"((?:www\.)?(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+"
    r"[A-Z]{2,63}(?:/[^\s<>\"']*)?)",
    re.IGNORECASE,
)
_ALLOWED_MAILTO_HEADERS = {"subject", "body", "cc", "bcc"}


def _trim_extracted_destination(value: str) -> str:
    """Remove prose punctuation that cannot be part of a trailing URL."""
    return value.strip().rstrip(".,;:!?")


def _normalised_hostname(value: str) -> str | None:
    try:
        hostname = urlsplit(value).hostname
    except ValueError:
        return None
    if not hostname:
        return None
    hostname = hostname.lower().rstrip(".")
    return hostname.removeprefix("www.")


def _is_source_domain(destination: str, source_url: str) -> bool:
    destination_host = _normalised_hostname(destination)
    source_host = _normalised_hostname(source_url)
    if not destination_host or not source_host:
        return False
    return (
        destination_host == source_host
        or destination_host.endswith(f".{source_host}")
        or source_host.endswith(f".{destination_host}")
    )


def _is_valid_email(value: str) -> bool:
    return _EMAIL_RE.fullmatch(value) is not None


def _validated_mailto(value: str) -> str | None:
    value = _trim_extracted_destination(value)
    if not value or _CONTROL_CHARACTER_RE.search(value):
        return None

    try:
        parsed = urlsplit(value)
        address = unquote(parsed.path)
        decoded_query = unquote(parsed.query)
    except (UnicodeDecodeError, ValueError):
        return None

    if parsed.scheme.lower() != "mailto" or parsed.netloc or parsed.fragment:
        return None
    if _CONTROL_CHARACTER_RE.search(address) or _CONTROL_CHARACTER_RE.search(decoded_query):
        return None
    if not _is_valid_email(address):
        return None

    for key, header_value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() not in _ALLOWED_MAILTO_HEADERS:
            return None
        if _CONTROL_CHARACTER_RE.search(key) or _CONTROL_CHARACTER_RE.search(header_value):
            return None
        if key.lower() in {"cc", "bcc"}:
            recipients = [recipient.strip() for recipient in header_value.split(",")]
            if not recipients or not all(_is_valid_email(recipient) for recipient in recipients):
                return None

    return value


def _validated_http_url(value: str, source_url: str) -> str | None:
    value = _trim_extracted_destination(value)
    if not value or any(character.isspace() for character in value):
        return None
    if _CONTROL_CHARACTER_RE.search(value):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None
    if parsed.hostname.lower() in {"http", "https"} and parsed.path.startswith("//"):
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    if source_url and _is_source_domain(value, source_url):
        return None
    return value


def is_safe_application_destination(destination: str, *, source_url: str = "") -> bool:
    """Return whether ``destination`` is a safe candidate-facing application action."""
    if not destination:
        return False
    if destination.lower().startswith("mailto:"):
        return _validated_mailto(destination) is not None
    return _validated_http_url(destination, source_url) is not None


def resolve_application_destination(
    *,
    application_instructions: str | None,
    source_url: str,
    job_title: str,
    candidate_url: str | None = None,
) -> str | None:
    """Resolve an explicit application action, never falling back to ``source_url``.

    A future scraper release may supply ``candidate_url`` directly. It is still validated
    here so a host cannot regress by passing the raw listing URL in that field.
    """
    if isinstance(candidate_url, str) and candidate_url:
        if candidate_url.lower().startswith("mailto:"):
            validated_candidate = _validated_mailto(candidate_url)
        else:
            validated_candidate = _validated_http_url(candidate_url, source_url)
        if validated_candidate:
            return validated_candidate

    instructions = application_instructions if isinstance(application_instructions, str) else ""

    for match in _MAILTO_URL_RE.finditer(instructions):
        destination = _validated_mailto(match.group(0))
        if destination:
            return destination

    for match in _HTTP_URL_RE.finditer(instructions):
        destination = _validated_http_url(match.group(0), source_url)
        if destination:
            return destination

    email_match = _EMAIL_RE.search(instructions)
    if email_match:
        subject = quote(job_title.strip(), safe="")
        destination = f"mailto:{email_match.group(0)}"
        if subject:
            destination = f"{destination}?subject={subject}"
        return _validated_mailto(destination)

    for match in _BARE_DOMAIN_RE.finditer(instructions):
        destination = _validated_http_url(f"https://{match.group(1)}", source_url)
        if destination:
            return destination

    return None
