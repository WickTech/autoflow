"""``${ENV_VAR}`` references in YAML.

Configs are committed; secrets are not. A value of exactly ``${NAME}`` is looked
up in the environment at runtime, which is why `autoflow validate` can warn about
unset references before a scheduled run discovers them the hard way.
"""
from __future__ import annotations

import os
import re

ENV_REF = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def ref_name(value: object) -> str | None:
    """Return the variable name if ``value`` is an ``${ENV_VAR}`` reference."""
    if not isinstance(value, str):
        return None
    match = ENV_REF.match(value.strip())
    return match.group(1) if match else None


def resolve(value: object, default: str = "") -> str:
    """Resolve an ``${ENV_VAR}`` reference; pass any other value through as a string."""
    if value is None:
        return default
    name = ref_name(value)
    if name is not None:
        return os.getenv(name, default)
    return str(value)
