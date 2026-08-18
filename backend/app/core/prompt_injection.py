"""
Prompt-injection defenses — Phase 9.

Untrusted text enters this system's LLM prompts from two places:
  1. The natural language requirement (directly user-supplied, highest risk).
  2. Knowledge Base text extracted from uploaded documents — table/column
     descriptions and business rule text (planning_agent.build_planning_prompt
     templates these in) — supplied by whoever uploaded the RDD/LDM, which
     may be a different, less-trusted party than whoever runs generation.

This is a deterministic, pattern-based detector — not an LLM-based one.
Using an LLM to detect prompt injection aimed at LLMs has an obvious
weakness (the detector itself is attackable via the same technique), and
a second model call adds latency/cost for a check that pattern-matching
handles well for the well-known injection phrasings this is meant to
catch. This is a defense-in-depth LAYER, not the primary defense — the
structural ones matter more and already exist:
  - ast_builder.py rejects any table/column/join not in the verified KB
    regardless of what a hijacked Planning Agent proposes.
  - generator_agent.py grounds its prompt in the already-validated AST,
    so even fully-hijacked prose can't smuggle in a fabricated table/column
    that later becomes real SQL.
This module's job is narrower and complementary: catch the attempt early
and either refuse (for direct user input, where refusing is cheap and the
user can rephrase) or flag-and-continue (for KB content, where refusing
outright would block legitimate ingestion over one bad sentence in a
500-row LDM — see document_parser.py's own hallucination-prevention
posture of flagging rather than blocking wherever reasonable).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Deliberately conservative and reviewable as a flat list — not a "smart"
# classifier — so a security reviewer can read every pattern this checks
# for in about a minute. Patterns target INSTRUCTION-OVERRIDE phrasing,
# not just any mention of related words (a business rule about "system
# access permissions" should not trip this; "ignore the above instructions"
# should).
_INJECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("ignore_instructions", re.compile(r"\bignore\s+(all\s+|the\s+)?(previous|prior|above|preceding)\s+instructions?\b", re.IGNORECASE)),
    ("disregard_instructions", re.compile(r"\bdisregard\s+(all\s+|the\s+)?(previous|prior|above|preceding)\b", re.IGNORECASE)),
    ("role_override", re.compile(r"\byou\s+are\s+now\s+(a|an)\b", re.IGNORECASE)),
    ("system_prompt_injection", re.compile(r"^\s*system\s*:", re.IGNORECASE | re.MULTILINE)),
    ("fake_delimiter_close", re.compile(r"</?(system|instructions?|prompt)>", re.IGNORECASE)),
    ("new_instructions_marker", re.compile(r"\bnew\s+instructions?\s*:", re.IGNORECASE)),
    ("reveal_system_prompt", re.compile(r"\b(reveal|print|show|output)\s+(your\s+)?(system\s+prompt|instructions)\b", re.IGNORECASE)),
    ("override_schema", re.compile(r"\bignore\s+(the\s+)?(schema|verified\s+tables?|knowledge\s+base)\b", re.IGNORECASE)),
]


@dataclass
class InjectionScanResult:
    matched_patterns: list[str] = field(default_factory=list)

    @property
    def is_suspicious(self) -> bool:
        return len(self.matched_patterns) > 0


def scan_for_injection(text: str) -> InjectionScanResult:
    """Pure, deterministic pattern scan. Returns every pattern name that
    matched — callers decide whether to refuse or just flag, based on
    trust level of the source (see module docstring)."""
    if not text:
        return InjectionScanResult()
    matched = [name for name, pattern in _INJECTION_PATTERNS if pattern.search(text)]
    return InjectionScanResult(matched_patterns=matched)


def sanitize_for_prompt_context(text: str) -> str:
    """
    Neutralizes characters/sequences that could let untrusted KB text break
    out of its intended "this is DATA, not an instruction" context inside a
    templated prompt — without mangling normal business language. This is
    NOT a replacement for scan_for_injection(); it's a second, independent
    layer (defense in depth: even a pattern this scanner doesn't recognize
    still can't use fenced-code-block or XML-tag tricks to escape context).
    """
    if not text:
        return text
    # Neutralize markdown code fences and XML/HTML-like tags that could be
    # used to fake a role/instruction boundary inside the prompt.
    text = text.replace("```", "'''")
    text = re.sub(r"</?(system|instructions?|prompt|assistant|user)>", "[filtered]", text, flags=re.IGNORECASE)
    return text
