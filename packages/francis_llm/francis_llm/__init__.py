from .local_ollama import build_chat_request, build_generate_request, chat, generate
from .router import (
    DEFAULT_OLLAMA_FAST_MODEL,
    DEFAULT_OLLAMA_HEAVY_MODEL,
    DEFAULT_OLLAMA_HOST,
    FAST_ROLE,
    HEAVY_ROLE,
    ModelRoute,
    classify_task_role,
    get_ollama_host,
    normalize_task_name,
    resolve_route,
    route_model,
)

__all__ = [
    "DEFAULT_OLLAMA_FAST_MODEL",
    "DEFAULT_OLLAMA_HEAVY_MODEL",
    "DEFAULT_OLLAMA_HOST",
    "FAST_ROLE",
    "HEAVY_ROLE",
    "ModelRoute",
    "build_chat_request",
    "build_generate_request",
    "chat",
    "classify_task_role",
    "generate",
    "get_ollama_host",
    "normalize_task_name",
    "resolve_route",
    "route_model",
]
