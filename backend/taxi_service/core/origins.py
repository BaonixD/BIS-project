from urllib.parse import urlsplit

_DEFAULT_PORTS = {"http": 80, "https": 443}


def normalize_origin(value: str) -> str:
    try:
        parts = urlsplit(value.strip())
        port = parts.port
    except ValueError:
        raise ValueError("origin must look like http(s)://host[:port]") from None
    scheme = parts.scheme.lower()
    if (
        scheme not in _DEFAULT_PORTS
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
        or "*" in parts.netloc
    ):
        raise ValueError("origin must look like http(s)://host[:port]")
    host = parts.hostname
    if ":" in host:
        host = f"[{host}]"
    if port is None or port == _DEFAULT_PORTS[scheme]:
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"
