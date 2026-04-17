"""Unit tests for NLPExtractor."""

import pytest
from lesson.graph.schema import RawEvent
from lesson.nlp.extractor import EntityKind, NLPExtractor


def make_event(**kwargs) -> RawEvent:
    defaults = {"tool": "Bash", "args": "", "result_head": "", "is_error": False, "significant": False}
    defaults.update(kwargs)
    return RawEvent(**defaults)


@pytest.fixture
def extractor():
    return NLPExtractor(use_spacy=False)  # regex-only for speed


class TestNLPExtractor:
    def test_extracts_error_code(self, extractor):
        ev = make_event(result_head="ModuleNotFoundError: No module named 'numpy'")
        entities = extractor.extract(ev)
        kinds = [e.kind for e in entities]
        assert EntityKind.error_code in kinds

    def test_extracts_version_string(self, extractor):
        ev = make_event(result_head="numpy 1.24.3 installed successfully")
        entities = extractor.extract(ev)
        versions = [e for e in entities if e.kind == EntityKind.version]
        assert any("1.24.3" in e.text for e in versions)

    def test_extracts_file_path(self, extractor):
        ev = make_event(
            tool="Edit",
            args='{"file_path": "/home/user/project/src/main.py"}',
        )
        entities = extractor.extract(ev)
        paths = [e for e in entities if e.kind == EntityKind.file_path]
        assert len(paths) > 0

    def test_extracts_package_name(self, extractor):
        ev = make_event(tool="Bash", args="pip install numpy")
        entities = extractor.extract(ev)
        pkgs = [e for e in entities if e.kind == EntityKind.package]
        assert any("numpy" in e.text for e in pkgs)

    def test_tool_name_always_present(self, extractor):
        ev = make_event(tool="Read", args="whatever")
        entities = extractor.extract(ev)
        tool_entities = [e for e in entities if e.kind == EntityKind.tool_name]
        assert len(tool_entities) == 1
        assert tool_entities[0].text == "Read"

    def test_no_duplicates(self, extractor):
        ev = make_event(
            result_head="ModuleNotFoundError ModuleNotFoundError ModuleNotFoundError"
        )
        entities = extractor.extract(ev)
        texts = [e.text for e in entities]
        assert len(texts) == len(set(texts))

    def test_concept_candidates_for_error_event(self, extractor):
        ev = make_event(result_head="AttributeError: 'NoneType' object has no attribute 'split'")
        candidates = extractor.concept_candidates(ev)
        assert len(candidates) > 0
        assert all(e.kind == EntityKind.error_code for e in candidates)

    def test_posix_error_extracted(self, extractor):
        ev = make_event(result_head="open: ENOENT: no such file or directory")
        entities = extractor.extract(ev)
        error_codes = [e.text for e in entities if e.kind == EntityKind.error_code]
        assert "ENOENT" in error_codes

    def test_bash_command_extracted(self, extractor):
        ev = make_event(tool="Bash", args="pytest tests/ -v")
        entities = extractor.extract(ev)
        cmds = [e for e in entities if e.kind == EntityKind.command]
        assert any("pytest" in e.text for e in cmds)
