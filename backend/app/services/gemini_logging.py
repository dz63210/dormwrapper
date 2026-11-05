"""Human-readable logging of outbound google-genai requests.

Dumps exactly what each AI stage sends to Gemini -- the model, the full
``system_instruction``, every ``contents`` part and the generation config --
so a request can be reproduced from the log. Binary parts (the room photo and
any other inline blob / file) are elided to a one-line summary; their bytes are
never written to the log.
"""
from __future__ import annotations

import logging
from app.config import settings

logger = logging.getLogger("app.services.gemini")


def _describe_part(part: object) -> str:
    """Render one ``contents`` part as text, eliding any binary blob."""
    if isinstance(part, str):
        return part

    inline = getattr(part, "inline_data", None)
    if inline is not None and getattr(inline, "data", None) is not None:
        mime = getattr(inline, "mime_type", None) or "?"
        return f"<inline blob omitted: {mime}, {len(inline.data)} bytes>"

    file_data = getattr(part, "file_data", None)
    if file_data is not None:
        uri = getattr(file_data, "file_uri", None) or "?"
        mime = getattr(file_data, "mime_type", None) or "?"
        return f"<file blob omitted: {uri} ({mime})>"

    text = getattr(part, "text", None)
    if text is not None:
        return str(text)

    return f"<part omitted: {type(part).__name__}>"


def log_gemini_request(*, label: str, model: str, contents: object, config: object) -> None:
    """INFO-log ``label`` plus the model, system instruction, contents and config."""
    if not settings.debug_ai_logging:
        logger.info("%s -> model=%s (request content omitted)", label, model)
        return
    parts = contents if isinstance(contents, list) else [contents]
    rendered = "\n--- next part ---\n".join(_describe_part(p) for p in parts)

    system_instruction = getattr(config, "system_instruction", None) or "(none)"
    extras = {
        key: value
        for key in ("response_mime_type", "response_modalities", "temperature")
        if (value := getattr(config, key, None)) is not None
    }

    logger.info(
        "%s -> model=%s\n"
        "===== system_instruction =====\n%s\n"
        "===== contents (%d part%s) =====\n%s\n"
        "===== config =====\n%s",
        label,
        model,
        system_instruction,
        len(parts),
        "" if len(parts) == 1 else "s",
        rendered,
        extras or "(defaults)",
    )
