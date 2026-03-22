<h1 align="center">crg-jedi</h1>

<p align="center">
  <strong>Code knowledge graph with real Python method resolution.</strong>
</p>

<p align="center">
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square" alt="MIT Licence"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10%2B-blue.svg?style=flat-square" alt="Python 3.10+"></a>
  <a href="https://modelcontextprotocol.io/"><img src="https://img.shields.io/badge/MCP-compatible-green.svg?style=flat-square" alt="MCP"></a>
</p>

---

> Built on [code-review-graph](https://github.com/tirth8205/code-review-graph) by [tirth8205](https://github.com/tirth8205).

## Why This Fork Exists

The original `code-review-graph` builds excellent file-level dependency graphs using Tree-sitter, supporting 12+ languages. However, **Python function-level call graphs don't work** — `callers_of` and `callees_of` queries return empty results because Tree-sitter parses syntax but can't resolve `self.method()` calls without type information.

This fork adds [jedi](https://github.com/davidhalter/jedi)-powered call resolution for Python. Jedi resolves method calls through mixin inheritance, cross-file imports, and re-exports — the same engine that powers Python autocomplete in editors like Vim and Emacs.

### Before vs. After

| Query | Original (Tree-sitter only) | crg-jedi (Tree-sitter + jedi) |
|-------|---------------------------|-------------------------------|
| `callers_of("MyClass.method")` | 0 results | 5+ callers across files |
| `callees_of("MyClass.method")` | 0 results | Resolved downstream calls |
| `tests_for("module.py")` | 0 results | Test files detected |
| `imports_of("module.py")` | Module names (no detail) | Named imports |
| Blast radius direction | Reverse only (importers) | Bidirectional (importers + imports) |
| Git worktree support | Not supported | `CRG_DB_PATH` env var |

### How Jedi Resolution Works

```
Tree-sitter (all languages)          Jedi (Python only)
─────────────────────────            ──────────────────
Parse AST → extract nodes       →   For each call site:
  (functions, classes, imports)       jedi.Script.goto(line, col)
                                      → resolves self.method()
Create CALLS edges with              → traces through mixins
  raw method names                    → follows cross-file imports
  (e.g., "_evaluate_promotion")       → returns qualified definition
                                  →   Replace raw edge target with
                                      resolved qualified name
```

Non-Python files (TypeScript, Go, Rust, Java, etc.) continue using Tree-sitter-only resolution, which works well for statically-typed languages.

---

## Quick Start

```bash
pip install crg-jedi
crg-jedi install    # registers MCP server in .mcp.json
```

Restart Claude Code, then:

```
Build the code review graph for this project
```

Initial build takes ~10-15 seconds (includes jedi analysis for Python files). Incremental updates are < 2 seconds.

### Git Worktree Support

If you use git worktrees, point all worktrees to a shared graph:

```bash
# In your .mcp.json, add env override:
{
  "mcpServers": {
    "crg-jedi": {
      "command": "uvx",
      "args": ["crg-jedi", "serve"],
      "env": {
        "CRG_DB_PATH": "/path/to/main/repo/.code-review-graph"
      }
    }
  }
}
```

---

## MCP Tools

### Core Tools (always loaded)

| Tool | Description |
|------|-------------|
| `build_or_update_graph_tool` | Full or incremental graph build |
| `get_impact_radius_tool` | Blast radius analysis of changed files |
| `query_graph_tool` | Predefined queries: `callers_of`, `callees_of`, `imports_of`, `importers_of`, `children_of`, `tests_for`, `inheritors_of`, `file_summary` |
| `get_review_context_tool` | Token-optimized review context with guidance |
| `semantic_search_nodes_tool` | Search by name or semantic similarity |
| `list_graph_stats_tool` | Graph statistics |
| `embed_graph_tool` | Compute vector embeddings for semantic search |
| `get_docs_section_tool` | Documentation retrieval |
| `run_extension` | Run analysis extensions (see below) |

### Extensions (lazy-loaded via `run_extension`)

Extensions are loaded on demand — zero token overhead until you use them.

```
run_extension(name="help")  →  list all available extensions
run_extension(name="dead_code")  →  find functions with no callers
```

| Extension | Description |
|-----------|-------------|
| `dead_code` | Find functions with no incoming CALLS edges |
| `test_gaps` | Find functions missing test coverage (direct or transitive) |
| `coupling` | Fan-in/fan-out metrics and instability scores |
| `cycles` | Circular import dependency detection |
| `change_risk` | Risk scoring: graph coupling × git churn × blast radius |
| `unused_imports` | Find imports with no downstream usage |
| `breaking_changes` | Detect signature changes and flag affected callers |
| `api_surface` | Map public interfaces (functions imported by other modules) |
| `dep_depth` | Dependency depth — longest import chain analysis |
| `multi_project` | Auto-detect Python subprojects for jedi scoping |
| `graph_diff` | Structural diff between git refs |
| `ts_resolver` | TypeScript call resolution (placeholder — Tree-sitter handles TS well) |

---

## Using with Subagents / Agent Teams

If you use Claude Code's custom agents (`.claude/agents/*.md`), subagents only have access to tools explicitly listed in their `tools:` frontmatter. **MCP tools are not included by default** — you must add them to any agent that should use crg-jedi.

### Which agents need crg-jedi tools?

Add crg-jedi tools to agents that do **code analysis** — auditing, dependency tracing, debugging, code review. Don't add them to pure implementation agents (they write code, not trace dependencies).

| Agent role | Recommended tools |
|-----------|-------------------|
| Codebase auditor / reviewer | `query_graph_tool`, `run_extension_tool`, `get_impact_radius_tool` |
| Dependency checker | `query_graph_tool`, `get_impact_radius_tool` |
| Debugger / investigator | `query_graph_tool`, `get_impact_radius_tool` |
| Strategy / code reviewer | `query_graph_tool`, `get_impact_radius_tool` |
| Implementation agents | Not needed — use grep fallback |

### Example: adding to an agent

```yaml
---
name: codebase-auditor
tools:
  - Read
  - Grep
  - Glob
  - mcp__crg-jedi__query_graph_tool
  - mcp__crg-jedi__run_extension_tool
  - mcp__crg-jedi__get_impact_radius_tool
---
```

The MCP tool names follow Claude Code's naming convention: `mcp__<server>__<tool>`. The server name is whatever you used in `.mcp.json` (default: `crg-jedi`).

### Graceful fallback

Always instruct agents to fall back to `Grep` if crg-jedi tools are unavailable or return errors. This makes the setup optional — agents work without crg-jedi, just with less accurate call resolution for Python.

---

## Supported Languages

All 12+ languages from the original are supported. Jedi enhances Python specifically.

| Language | Parsing | Call Resolution |
|----------|---------|----------------|
| **Python** | Tree-sitter | Tree-sitter + **jedi** |
| TypeScript/JavaScript/TSX | Tree-sitter | Tree-sitter |
| Go | Tree-sitter | Tree-sitter |
| Rust | Tree-sitter | Tree-sitter |
| Java | Tree-sitter | Tree-sitter |
| C# | Tree-sitter | Tree-sitter |
| C/C++ | Tree-sitter | Tree-sitter |
| Ruby | Tree-sitter | Tree-sitter |
| Kotlin | Tree-sitter | Tree-sitter |
| Swift | Tree-sitter | Tree-sitter |
| PHP | Tree-sitter | Tree-sitter |

---

## Configuration

### `.code-review-graphignore`

Exclude paths from indexing (same syntax as `.gitignore`):

```
node_modules/**
.venv/**
__pycache__/**
*.generated.ts
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `CRG_DB_PATH` | Override graph database location (for worktrees) |
| `NO_COLOR` | Disable colored CLI output |

---

## Development

```bash
git clone https://github.com/tora-san/crg-jedi.git
cd crg-jedi
uv venv && uv pip install -e ".[dev]"
pytest
```

### Syncing with upstream

```bash
git remote add upstream https://github.com/tirth8205/code-review-graph.git
git fetch upstream
git merge upstream/main
```

---

## License

MIT — same as the original. See [LICENSE](LICENSE).

## Credits

- Original [code-review-graph](https://github.com/tirth8205/code-review-graph) by [tirth8205](https://github.com/tirth8205) — the Tree-sitter parsing, SQLite graph engine, MCP server, and core tools
- [jedi](https://github.com/davidhalter/jedi) by David Halter — Python static analysis powering the call resolution
- This fork by [tora-san](https://github.com/tora-san) — jedi integration, bug fixes, extensions, worktree support
