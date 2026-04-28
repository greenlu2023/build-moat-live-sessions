from urllib.parse import urlparse

MAX_URL_LENGTH = 2048

BLOCKED_DOMAINS = {
    "evil.com",
    "malware.example.com",
    "phishing.example.com",
}


def is_blocked_domain(hostname: str | None) -> bool:
    if hostname is None:
        return True
    return hostname.lower() in BLOCKED_DOMAINS


def validate_url(url: str) -> str:
    """Format check, normalization, and blocklist validation."""
    if len(url) > MAX_URL_LENGTH:
        raise ValueError(f"URL length exceeds maximum of {MAX_URL_LENGTH}")
        
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL scheme must be http or https")
        
    if is_blocked_domain(parsed.hostname):
        raise ValueError("URL domain is blocked")
        
    normalized = url.lower().rstrip("/")
    if normalized.startswith("http://"):
        normalized = "https://" + normalized[7:]
        
    return normalized
