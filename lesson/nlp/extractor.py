"""NLP entity extractor for arc.jsonl events using spaCy.

Extracts structured entities (file paths, version strings, error codes, tool
names) that become node labels in the session knowledge graph.
LLM-free — uses rule-based matching only (no GPU, no model inference).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lesson.graph.schema import RawEvent

# Lazy spaCy import so the package is importable without the model installed
_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        import spacy
        from spacy.language import Language

        try:
            _nlp = spacy.load("en_core_web_sm", disable=["ner", "parser", "lemmatizer"])
        except OSError:
            # Fallback: blank English pipeline (no model required)
            _nlp = spacy.blank("en")

        _add_entity_ruler(_nlp)
    return _nlp


def _add_entity_ruler(nlp):
    from spacy.pipeline import EntityRuler

    ruler = nlp.add_pipe("entity_ruler", last=True)

    # File paths  /foo/bar.py  ./src/main.ts
    ruler.add_patterns([
        {"label": "FILE_PATH", "pattern": [{"TEXT": {"REGEX": r"\.?/[\w.\-/]+"}}]},
    ])

    # Version strings  3.10.12  v2.1  1.0.0-beta
    ruler.add_patterns([
        {"label": "VERSION", "pattern": [{"TEXT": {"REGEX": r"v?\d+\.\d+[\w.\-]*"}}]},
    ])

    # Python exception names  ModuleNotFoundError  AttributeError
    ruler.add_patterns([
        {"label": "ERROR_CODE", "pattern": [{"TEXT": {"REGEX": r"[A-Z][a-zA-Z]*Error"}}]},
        {"label": "ERROR_CODE", "pattern": [{"TEXT": {"REGEX": r"[A-Z][a-zA-Z]*Exception"}}]},
        # POSIX error codes ENOENT EPERM
        {"label": "ERROR_CODE", "pattern": [{"TEXT": {"REGEX": r"E[A-Z]{2,8}"}}]},
        # HTTP status codes 404 500 etc.
        {"label": "ERROR_CODE", "pattern": [{"TEXT": {"REGEX": r"[45]\d{2}"}}]},
    ])


class EntityKind(str, Enum):
    file_path = "FILE_PATH"
    version = "VERSION"
    error_code = "ERROR_CODE"
    tool_name = "TOOL_NAME"
    package = "PACKAGE"
    command = "COMMAND"
    unknown = "UNKNOWN"


@dataclass(frozen=True)
class Entity:
    text: str
    kind: EntityKind
    source: str = ""  # which field of RawEvent it came from

    def __str__(self) -> str:
        return self.text


# Regex-based extractors (no spaCy needed for these)
_PATH_RE = re.compile(r"(?:\.{0,2}/[\w.\-]+){2,}")
_VERSION_RE = re.compile(r"\bv?\d+\.\d+[\w.\-]*\b")
_ERROR_NAME_RE = re.compile(r"\b([A-Z][a-zA-Z]*(?:Error|Exception|Warning))\b")
_POSIX_ERR_RE = re.compile(r"\b(E[A-Z]{2,8})\b")
_CMD_RE = re.compile(r"^([\w.\-]+)\s")  # first token of a Bash args string
_PKG_RE = re.compile(r"\b(?:pip install|npm install|yarn add|apt install)\s+([\w\-@/]+)")


class NLPExtractor:
    """Extract structured entities from a RawEvent.

    Uses regex patterns for speed; spaCy EntityRuler for anything the regexes
    miss. Falls back gracefully if spaCy model is unavailable.
    """

    def __init__(self, use_spacy: bool = True) -> None:
        self._use_spacy = use_spacy

    def extract(self, event: "RawEvent") -> list[Entity]:
        entities: list[Entity] = []
        text_args = event.args or ""
        text_result = event.result_head or ""

        # Tool name itself is always an entity
        if event.tool and event.tool != "unknown":
            entities.append(Entity(event.tool, EntityKind.tool_name, "tool"))

        # File paths
        for m in _PATH_RE.finditer(text_args + " " + text_result):
            entities.append(Entity(m.group(), EntityKind.file_path, "text"))

        # Version strings
        for m in _VERSION_RE.finditer(text_args + " " + text_result):
            entities.append(Entity(m.group(), EntityKind.version, "text"))

        # Error names
        for m in _ERROR_NAME_RE.finditer(text_result):
            entities.append(Entity(m.group(1), EntityKind.error_code, "result"))
        for m in _POSIX_ERR_RE.finditer(text_result):
            entities.append(Entity(m.group(1), EntityKind.error_code, "result"))

        # Package installs
        for m in _PKG_RE.finditer(text_args):
            entities.append(Entity(m.group(1), EntityKind.package, "args"))

        # Bash first command token
        if event.tool == "Bash":
            m = _CMD_RE.match(text_args.strip())
            if m:
                entities.append(Entity(m.group(1), EntityKind.command, "args"))

        # Deduplicate preserving order
        seen: set[tuple[str, EntityKind]] = set()
        unique: list[Entity] = []
        for e in entities:
            key = (e.text.lower(), e.kind)
            if key not in seen:
                seen.add(key)
                unique.append(e)

        return unique

    def extract_batch(self, events: list["RawEvent"]) -> dict[str, list[Entity]]:
        """Return {event_tool_ts: [entities]} map."""
        return {f"{e.tool}@{e.ts:.0f}": self.extract(e) for e in events}

    def concept_candidates(self, event: "RawEvent") -> list[Entity]:
        """Return entities that are plausible concept node labels."""
        return [
            e for e in self.extract(event)
            if e.kind in (EntityKind.error_code, EntityKind.package, EntityKind.file_path)
        ]
