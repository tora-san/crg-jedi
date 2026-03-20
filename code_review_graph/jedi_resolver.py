"""Jedi-powered Python call resolution.

Enhances Tree-sitter's syntactic call detection with jedi's semantic
type inference, resolving self.method() calls through mixin inheritance,
cross-file imports, and re-exports.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import jedi
    JEDI_AVAILABLE = True
except ImportError:
    JEDI_AVAILABLE = False


@dataclass
class CallSite:
    """A function call found by Tree-sitter."""
    caller_qualified_name: str
    raw_call_name: str
    line: int
    column: int
    file_path: str


@dataclass
class ResolvedCall:
    """A call resolved by jedi to a specific definition."""
    source_qualified: str  # caller's qualified name
    target_qualified: str  # resolved definition's qualified name
    target_file: str       # file containing the definition
    target_line: int       # line of the definition
    line: int              # line of the call site


class JediResolver:
    """Resolves Python call sites to their definitions using jedi."""

    def __init__(self, project_path: str | Path) -> None:
        if not JEDI_AVAILABLE:
            raise RuntimeError("jedi is not installed. Install with: pip install jedi")
        self.project = jedi.Project(path=str(project_path))
        self._scripts: dict[str, jedi.Script] = {}

    def _get_script(self, file_path: str) -> jedi.Script:
        if file_path not in self._scripts:
            self._scripts[file_path] = jedi.Script(
                path=file_path, project=self.project
            )
        return self._scripts[file_path]

    def resolve_calls(
        self, file_path: str, call_sites: list[CallSite]
    ) -> list[ResolvedCall]:
        """Resolve call sites in a file to their definitions."""
        if not call_sites:
            return []

        try:
            script = self._get_script(file_path)
        except Exception as e:
            logger.debug("Failed to create jedi script for %s: %s", file_path, e)
            return []

        resolved = []
        for site in call_sites:
            try:
                defs = script.goto(site.line, site.column)
                if not defs:
                    continue
                d = defs[0]
                if d.module_path is None:
                    continue

                # Build qualified name matching the graph's convention:
                # file_path::ClassName.method_name or file_path::function_name
                target_file = str(d.module_path)
                target_name = d.name

                # Check if it's a method (has a parent class)
                parent = d.parent()
                if parent and parent.type == 'class':
                    target_qualified = f"{target_file}::{parent.name}.{target_name}"
                else:
                    target_qualified = f"{target_file}::{target_name}"

                resolved.append(ResolvedCall(
                    source_qualified=site.caller_qualified_name,
                    target_qualified=target_qualified,
                    target_file=target_file,
                    target_line=d.line or 0,
                    line=site.line,
                ))
            except Exception as e:
                logger.debug(
                    "Failed to resolve %s at %s:%d: %s",
                    site.raw_call_name, file_path, site.line, e,
                )
        return resolved

    def clear_cache(self) -> None:
        """Clear cached jedi scripts (call after file changes)."""
        self._scripts.clear()
