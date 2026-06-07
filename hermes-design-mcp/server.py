#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hermes-design-mcp — FastMCP SSE server wrapping the UI/UX design knowledge base.
Port: 8012 (configurable via PORT env var)
"""

import json
import os
import re
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings


# --- startup CSV validation ---------------------------------------------------
def _validate():
    from core import DATA_DIR
    expected = [
        "styles.csv", "colors.csv", "products.csv", "typography.csv",
        "google-fonts.csv", "charts.csv", "ux-guidelines.csv", "icons.csv",
        "landing.csv", "react-performance.csv", "app-interface.csv",
        "design.csv", "draft.csv", "ui-reasoning.csv",
    ]
    missing = [f for f in expected if not (DATA_DIR / f).exists()]
    if missing:
        print(f"[hermes-design-mcp] DATA_DIR={DATA_DIR}", file=sys.stderr)
        print(f"[hermes-design-mcp] Missing CSVs: {missing}", file=sys.stderr)
        sys.exit(1)


_validate()

# --- imports (after validation so missing CSVs surface immediately) -----------
from core import search as _search, search_stack as _search_stack, DATA_DIR  # noqa: E402
from design_system import generate_design_system as _gen_ds  # noqa: E402

_ANSI_ESC = re.compile(r"\x1b\[[0-9;]*m")

mcp = FastMCP(
    "hermes-design",
    transport_security=TransportSecuritySettings(
        allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", "host.docker.internal:*"],
    ),
)

VALID_DOMAINS = {
    "style", "color", "product", "typography", "google-fonts",
    "chart", "ux", "landing", "icons", "web", "react",
}
VALID_STACKS = {
    "react", "nextjs", "angular", "vue", "svelte", "astro",
    "swiftui", "react-native", "flutter", "nuxtjs",
    "html-tailwind", "shadcn", "tailwind",
}


@mcp.tool()
def design_search(query: str, domain: str = None, max_results: int = 5) -> str:
    """BM25 search over UI/UX design knowledge base.

    Args:
        query: Natural language search query.
        domain: Optional domain filter. One of: style, color, product, typography,
                google-fonts, chart, ux, landing, icons, web, react.
        max_results: Maximum number of results to return (default 5).

    Returns:
        JSON string with search results.
    """
    if domain is not None and domain not in VALID_DOMAINS:
        raise ValueError(f"domain must be one of {sorted(VALID_DOMAINS)}")
    results = _search(query, domain, max_results)
    return json.dumps(results, ensure_ascii=False, indent=2)


@mcp.tool()
def design_search_stack(query: str, stack: str, max_results: int = 5) -> str:
    """Stack-specific UI/UX design guidance.

    Args:
        query: Natural language search query.
        stack: Framework/stack name. One of: react, nextjs, angular, vue, svelte,
               astro, swiftui, react-native, flutter, nuxtjs, html-tailwind, shadcn, tailwind.
        max_results: Maximum number of results to return (default 5).

    Returns:
        JSON string with stack-specific guidance results.
    """
    if stack not in VALID_STACKS:
        raise ValueError(f"stack must be one of {sorted(VALID_STACKS)}")
    results = _search_stack(query, stack, max_results)
    return json.dumps(results, ensure_ascii=False, indent=2)


@mcp.tool()
def design_system(query: str, project_name: str = "project") -> str:
    """Generate a full Markdown design system for a project.

    Aggregates results across multiple design domains (product, style, color,
    landing, typography) and applies UI reasoning rules to produce a cohesive
    design system document.

    Args:
        query: Description of the project (e.g. "SaaS dashboard", "e-commerce app").
        project_name: Name of the project (used in output headings).

    Returns:
        Markdown string with the complete design system recommendation.
    """
    raw = _gen_ds(query, project_name)
    return _ANSI_ESC.sub("", raw)


mcp.settings.host = "0.0.0.0"
mcp.settings.port = int(os.environ.get("PORT", 8012))

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
