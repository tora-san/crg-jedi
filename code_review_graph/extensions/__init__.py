"""Extension auto-discovery and registration.

Extensions are loaded lazily via the run_extension MCP tool.
Each extension module must define:
  - EXTENSION_NAME: str — unique identifier
  - EXTENSION_DESCRIPTION: str — one-line description
  - run(**kwargs) -> dict — the extension entry point
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Map of extension name -> module name
_EXTENSION_MODULES = {
    "dead_code": ".dead_code",
    "test_gaps": ".test_gaps",
    "coupling": ".coupling",
    "cycles": ".cycles",
    "change_risk": ".change_risk",
    "multi_project": ".multi_project",
    "graph_diff": ".graph_diff",
    "ts_resolver": ".ts_resolver",
    "unused_imports": ".unused_imports",
    "breaking_changes": ".breaking_changes",
    "api_surface": ".api_surface",
    "dep_depth": ".dep_depth",
}

_loaded_extensions: dict[str, Any] = {}


def _load_extension(name: str) -> Optional[Any]:
    """Load an extension module by name."""
    if name in _loaded_extensions:
        return _loaded_extensions[name]

    module_name = _EXTENSION_MODULES.get(name)
    if not module_name:
        return None

    try:
        mod = importlib.import_module(module_name, package=__package__)
        _loaded_extensions[name] = mod
        return mod
    except Exception as e:
        logger.debug("Failed to load extension '%s': %s", name, e)
        return None


def get_extension(name: str) -> Optional[Callable]:
    """Get the run() function for an extension."""
    mod = _load_extension(name)
    if mod and hasattr(mod, "run"):
        return mod.run
    return None


def list_extensions() -> list[dict[str, str]]:
    """List all available extensions with descriptions."""
    result = []
    for name in _EXTENSION_MODULES:
        mod = _load_extension(name)
        if mod:
            result.append({
                "name": name,
                "description": getattr(mod, "EXTENSION_DESCRIPTION", "No description"),
            })
        else:
            result.append({
                "name": name,
                "description": "(failed to load)",
            })
    return result
