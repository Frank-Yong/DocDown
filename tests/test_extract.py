"""Tests for Stage 2 content extraction via GROBID."""

from __future__ import annotations

import logging
import os

import pytest
import requests

from docdown.stages.extract import GrobidError, extract_grobid_chunk, wait_for_grobid


class _Resp:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text


def test_wait_for_grobid_becomes_ready(monkeypatch):
    responses = iter([
        _Resp(503, "starting"),
        _Resp(200, "true"),
    ])

    def _fake_get(url, timeout):
        return next(responses)

    monkeypatch.setattr("docdown.stages.extract.requests.get", _fake_get)
    monkeypatch.setattr("docdown.stages.extract.time.sleep", lambda *_: None)

    wait_for_grobid("http://localhost:8070", max_wait=5, poll_interval=1)


def test_wait_for_grobid_does_not_accept_untrue(monkeypatch):
    responses = iter([
        _Resp(200, "untrue"),
        _Resp(200, " true\n"),
    ])

    def _fake_get(url, timeout):
        return next(responses)

    monkeypatch.setattr("docdown.stages.extract.requests.get", _fake_get)
    monkeypatch.setattr("docdown.stages.extract.time.sleep", lambda *_: None)

    wait_for_grobid("http://localhost:8070", max_wait=5, poll_interval=1)


def test_wait_for_grobid_timeout_raises_clear_error(monkeypatch):
    def _fake_get(url, timeout):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr("docdown.stages.extract.requests.get", _fake_get)
    monkeypatch.setattr("docdown.stages.extract.time.sleep", lambda *_: None)

    with pytest.raises(GrobidError, match="did not become ready"):
        wait_for_grobid("http://localhost:8070", max_wait=1, poll_interval=1)


def test_extract_grobid_chunk_writes_xml_and_logs_time(tmp_path, monkeypatch, caplog):
    chunk = tmp_path / "chunk-0001.pdf"
    output = tmp_path / "extracted" / "chunk-0001.xml"
    chunk.write_bytes(b"%PDF-1.4\n")

    def _fake_post(url, files, timeout):
        return _Resp(200, "<TEI>ok</TEI>")

    monkeypatch.setattr("docdown.stages.extract.requests.post", _fake_post)
    test_logger = logging.getLogger("tests.extract")

    with caplog.at_level(logging.INFO, logger="tests.extract"):
        result = extract_grobid_chunk(chunk, output, "http://localhost:8070", logger=test_logger)

    assert result == output
    assert output.read_text(encoding="utf-8") == "<TEI>ok</TEI>"
    assert "GROBID extraction complete" in caplog.text


def test_extract_grobid_chunk_uses_provided_logger_with_chunk_context(tmp_path, monkeypatch, caplog):
    chunk = tmp_path / "chunk-0001.pdf"
    output = tmp_path / "chunk-0001.xml"
    chunk.write_bytes(b"%PDF-1.4\n")

    def _fake_post(url, files, timeout):
        return _Resp(200, "<TEI>ok</TEI>")

    monkeypatch.setattr("docdown.stages.extract.requests.post", _fake_post)
    custom_logger = logging.getLogger("tests.extract.custom")

    with caplog.at_level(logging.INFO, logger="tests.extract.custom"):
        extract_grobid_chunk(
            chunk,
            output,
            "http://localhost:8070",
            logger=custom_logger,
            chunk_number=7,
        )

    matching = [
        record
        for record in caplog.records
        if record.name == "tests.extract.custom" and "GROBID extraction complete" in record.getMessage()
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "chunk", None) == "chunk-0007"


def test_extract_grobid_chunk_timeout_retries_once_with_doubled_timeout(tmp_path, monkeypatch):
    chunk = tmp_path / "chunk-0001.pdf"
    output = tmp_path / "chunk-0001.xml"
    chunk.write_bytes(b"%PDF-1.4\n")
    seen_timeouts: list[int] = []
    call_count = {"n": 0}

    def _fake_post(url, files, timeout):
        seen_timeouts.append(timeout)
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise requests.Timeout("first timeout")
        return _Resp(200, "<TEI>ok</TEI>")

    monkeypatch.setattr("docdown.stages.extract.requests.post", _fake_post)

    extract_grobid_chunk(chunk, output, "http://localhost:8070", timeout=120, retries_on_503=0)
    assert seen_timeouts == [120, 240]


def test_extract_grobid_chunk_503_uses_exponential_backoff(tmp_path, monkeypatch):
    chunk = tmp_path / "chunk-0001.pdf"
    output = tmp_path / "chunk-0001.xml"
    chunk.write_bytes(b"%PDF-1.4\n")

    responses = iter([
        _Resp(503, "busy 1"),
        _Resp(503, "busy 2"),
        _Resp(503, "busy 3"),
        _Resp(200, "<TEI>ok</TEI>"),
    ])
    sleeps: list[int] = []

    def _fake_post(url, files, timeout):
        return next(responses)

    monkeypatch.setattr("docdown.stages.extract.requests.post", _fake_post)
    monkeypatch.setattr("docdown.stages.extract.time.sleep", lambda s: sleeps.append(s))

    extract_grobid_chunk(chunk, output, "http://localhost:8070", retries_on_503=3, backoff_base_seconds=5)
    assert sleeps == [5, 10, 20]


def test_extract_grobid_chunk_timeout_then_503_starts_backoff_at_base(tmp_path, monkeypatch):
    chunk = tmp_path / "chunk-0001.pdf"
    output = tmp_path / "chunk-0001.xml"
    chunk.write_bytes(b"%PDF-1.4\n")

    seen_timeouts: list[int] = []
    sleeps: list[int] = []
    call_count = {"n": 0}

    def _fake_post(url, files, timeout):
        seen_timeouts.append(timeout)
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise requests.Timeout("first timeout")
        if call_count["n"] == 2:
            return _Resp(503, "busy")
        return _Resp(200, "<TEI>ok</TEI>")

    monkeypatch.setattr("docdown.stages.extract.requests.post", _fake_post)
    monkeypatch.setattr("docdown.stages.extract.time.sleep", lambda s: sleeps.append(s))

    extract_grobid_chunk(chunk, output, "http://localhost:8070", retries_on_503=3, backoff_base_seconds=5)

    assert seen_timeouts == [120, 240, 240]
    assert sleeps == [5]


def test_extract_grobid_chunk_reports_nonrecoverable_http_error(tmp_path, monkeypatch):
    chunk = tmp_path / "chunk-0001.pdf"
    output = tmp_path / "chunk-0001.xml"
    chunk.write_bytes(b"%PDF-1.4\n")

    def _fake_post(url, files, timeout):
        return _Resp(400, "bad request details")

    monkeypatch.setattr("docdown.stages.extract.requests.post", _fake_post)

    with pytest.raises(GrobidError, match="HTTP 400"):
        extract_grobid_chunk(chunk, output, "http://localhost:8070")


@pytest.mark.integration
def test_extract_grobid_chunk_integration_real_service(tmp_path):
    if os.environ.get("RUN_GROBID_INTEGRATION") != "1":
        pytest.skip("Set RUN_GROBID_INTEGRATION=1 to run GROBID container integration test")

    fitz = pytest.importorskip("fitz")
    chunk = tmp_path / "chunk-0001.pdf"
    output = tmp_path / "chunk-0001.xml"

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "DocDown integration test")
    doc.save(chunk)

    wait_for_grobid("http://localhost:8070", max_wait=60)
    result = extract_grobid_chunk(chunk, output, "http://localhost:8070", timeout=120)

    assert result.exists()
    assert "<TEI" in result.read_text(encoding="utf-8")
