"""
skill_injector.py — LiteLLM CustomLogger that auto-injects matching coding-standard
skills into the system message before each request.
"""
from __future__ import annotations

from litellm.integrations.custom_logger import CustomLogger
import os
import re
import glob
import logging
import yaml
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKILLS_DIR = os.path.expanduser("~/.claude/skills")
MAX_SKILLS = 5
EXCLUDED_PREFIXES = ("sdd-", "skill-")
EXCLUDED_NAMES = {
    "_shared",
    "cognitive-doc-design",
    "comment-writer",
    "issue-creation",
    "judgment-day",
}

_STOPWORDS = {
    "when", "the", "with", "for", "code", "a", "an", "writing", "using",
    "building", "use", "this", "skill", "trigger", "is", "in", "or", "and",
    "are", "you", "your", "to", "of", "it", "on", "as", "at", "by", "we", "if",
}

_KNOWN_EXTENSIONS = {".tsx", ".ts", ".jsx", ".cs", ".csproj", ".py", ".go"}

# Maps terms found in descriptions to file extensions / keyword signals
_LANG_ALIASES: dict[str, list[str]] = {
    "c#":         [".cs", "csharp", "dotnet"],
    "csharp":     [".cs"],
    ".net":       [".cs", "dotnet"],
    "typescript": [".ts"],
    "javascript": [".js"],
    "python":     [".py"],
    "golang":     [".go"],
    "react":      [".tsx", ".jsx"],
    "nextjs":     [".tsx"],
    "next.js":    [".tsx"],
    "angular":    [".ts"],
    "django":     [".py"],
    "pytest":     [".py"],
    "playwright": [".ts", ".tsx"],
    "zustand":    [".tsx", ".ts"],
    "tailwind":   [".tsx", ".html"],
    "zod":        [".ts", ".tsx"],
}

# Module-level cache for loaded reference files
_file_cache: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class SkillEntry:
    def __init__(self, name: str, keywords: set, skill_md_path: str, body: Optional[str] = None, router: Optional[list] = None):
        self.name = name
        self.keywords = keywords
        self.skill_md_path = skill_md_path
        self.body = body
        self.router = router if router is not None else []


# ---------------------------------------------------------------------------
# SkillInjector
# ---------------------------------------------------------------------------

class SkillInjector(CustomLogger):

    def __init__(self):
        super().__init__()
        self.index: list[SkillEntry] = self._build_index()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_excluded(self, name: str) -> bool:
        if name.startswith(EXCLUDED_PREFIXES):
            return True
        return name in EXCLUDED_NAMES

    def _parse_frontmatter(self, text: str) -> tuple[dict, str]:
        """Return (meta_dict, body_text). Handles missing front matter gracefully."""
        if text.startswith("---"):
            parts = text.split("---", 2)
            # parts[0] = "" (before first ---), parts[1] = YAML, parts[2] = body
            if len(parts) == 3:
                try:
                    meta = yaml.safe_load(parts[1]) or {}
                    return meta, parts[2]
                except Exception:
                    return {}, text
        return {}, text

    def _extract_keywords(self, description: str, name: str) -> set[str]:
        """Extract keyword set from the Trigger sentence in description."""
        keywords: set[str] = set()

        # Always add name and its hyphen-split tokens
        keywords.add(name.lower())
        for token in name.lower().split("-"):
            if token:
                keywords.add(token)

        # Find "Trigger:" text
        trigger_text = ""
        match = re.search(r"trigger\s*:", description, re.IGNORECASE)
        if match:
            after = description[match.end():]
            # Take up to the next period or end of string
            period = after.find(".")
            trigger_text = after[:period] if period != -1 else after

        # Tokenize and filter stopwords
        tokens = re.split(r"\W+", trigger_text.lower())
        for token in tokens:
            if token and token not in _STOPWORDS:
                keywords.add(token)

        # Scan full description for known extensions and language aliases
        description_lower = description.lower()
        for ext in _KNOWN_EXTENSIONS:
            if ext in description_lower:
                keywords.add(ext)
        for term, aliases in _LANG_ALIASES.items():
            if term in description_lower:
                keywords.update(aliases)

        return keywords

    def _parse_router(self, body: str, skill_dir: str) -> list[tuple[set[str], str]]:
        """Parse Topic Router table rows from SKILL.md body."""
        rows = []
        for line in body.splitlines():
            # Look for table rows with a backtick-quoted reference file
            backtick_match = re.search(r"`(references/[^`]+\.md)`", line)
            if not backtick_match:
                continue
            ref_filename = backtick_match.group(1)
            abspath = os.path.join(skill_dir, ref_filename)
            if not os.path.exists(abspath):
                continue

            # Extract non-backtick, non-pipe cell content as trigger text
            # Remove the backtick portion and pipe separators
            clean = re.sub(r"`[^`]+`", "", line)
            clean = clean.replace("|", " ")
            tokens = re.split(r"\W+", clean.lower())
            kw_set = {t for t in tokens if t and t not in _STOPWORDS}
            rows.append((kw_set, abspath))
        return rows

    def _build_index(self) -> list[SkillEntry]:
        """Glob all SKILL.md files, parse and index them."""
        paths = sorted(glob.glob(os.path.join(SKILLS_DIR, "*/SKILL.md")))
        result: list[SkillEntry] = []

        for path in paths:
            try:
                skill_dir = os.path.dirname(path)
                folder_name = os.path.basename(skill_dir)

                if self._is_excluded(folder_name):
                    continue

                text = open(path, encoding="utf-8").read()
                meta, body = self._parse_frontmatter(text)
                name = meta.get("name", folder_name) if isinstance(meta, dict) else folder_name
                description = meta.get("description", "") if isinstance(meta, dict) else ""
                keywords = self._extract_keywords(description, folder_name)
                router = self._parse_router(body, skill_dir)

                entry = SkillEntry(
                    name=name,
                    keywords=keywords,
                    skill_md_path=path,
                    body=None,
                    router=router,
                )
                result.append(entry)

            except Exception as exc:
                logging.warning("SkillInjector: skipping %s — %s", path, exc)

        logging.info("SkillInjector: indexed %d skills", len(result))
        return result

    def _score(self, entry: SkillEntry, haystack: str) -> int:
        """Count distinct keywords from entry that appear as substrings in haystack."""
        return sum(1 for kw in entry.keywords if kw in haystack)

    def _resolve_content(self, entry: SkillEntry, haystack: str) -> str:
        """Return the most-relevant content: router sub-file if matched, else body."""
        if entry.router:
            best_score = 0
            best_path = None
            for kw_set, abspath in entry.router:
                score = sum(1 for kw in kw_set if kw in haystack)
                if score > best_score:
                    best_score = score
                    best_path = abspath

            if best_path and best_score > 0:
                if best_path not in _file_cache:
                    _file_cache[best_path] = open(best_path, encoding="utf-8").read()
                return _file_cache[best_path]

        # Fallback: lazy-load full SKILL.md body
        if entry.body is None:
            text = open(entry.skill_md_path, encoding="utf-8").read()
            _, body = self._parse_frontmatter(text)
            entry.body = body

        return entry.body

    def _append_system(self, msgs: list, text: str) -> None:
        """Append text to the system message, or insert one if absent."""
        for msg in msgs:
            if msg.get("role") == "system":
                content = msg.get("content")
                if isinstance(content, str):
                    msg["content"] += text
                elif isinstance(content, list):
                    content.append({"type": "text", "text": text})
                return
        # No system message found — insert one at the front
        msgs.insert(0, {"role": "system", "content": text})

    # ------------------------------------------------------------------
    # LiteLLM hook
    # ------------------------------------------------------------------

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        return response

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        try:
            msgs = data.get("messages", [])
            haystack = " ".join(
                str(m.get("content", "")) for m in msgs
                if m.get("role") in ("user", "tool")
            ).lower()

            scored = sorted(
                ((self._score(e, haystack), e) for e in self.index),
                key=lambda t: t[0],
                reverse=True,
            )
            picks = [e for s, e in scored if s > 0][:MAX_SKILLS]

            if not picks:
                return data

            blocks = [self._resolve_content(e, haystack) for e in picks]
            inject = "\n\n# Coding Standards (auto-injected)\n\n" + "\n\n---\n\n".join(blocks)
            self._append_system(msgs, inject)

        except Exception as exc:
            logging.warning("SkillInjector skipped: %s", exc)

        return data


skill_injector_instance = SkillInjector()
