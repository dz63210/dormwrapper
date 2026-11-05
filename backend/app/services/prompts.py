"""Load prompt / instruction documents from disk, once per path.

Both AI stages of the "generate design" flow are steered by a plain-text
document on disk (see ``app/prompts/``):

* ``settings.recommendation_prompt_path`` - instructs the Stage 1 furniture
  recommender (text -> structured JSON).
* ``settings.image_gen_context_path`` - instructs the Stage 2 image model.

A missing file is tolerated: we log a warning and return an empty string so
the flow keeps working (the model just runs without extra instructions).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_cache: dict[str, str] = {}


def load_prompt(path: str) -> str:
    """Return the contents of the prompt file at ``path``, cached after first read."""
    if path not in _cache:
        try:
            with open(path, encoding="utf-8") as fh:
                _cache[path] = fh.read().strip()
            logger.info("Loaded prompt document from %s (%d chars).", path, len(_cache[path]))
        except OSError as exc:
            logger.warning(
                "Prompt document not available at %s (%s); the model will run "
                "with no extra instructions.", path, exc,
            )
            _cache[path] = ""
    return _cache[path]
