def redact(text: str) -> str:
    return text.replace("token", "[REDACTED]").replace("password", "[REDACTED]")
