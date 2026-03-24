"""Tests for Stage 2 content extraction via GROBID and pdfminer fallback."""

from __future__ import annotations

import logging
import os

import pytest
import requests

from docdown.stages.extract import (
    ExtractorUsed,
    ExtractionResult,
    GrobidError,
    PdfMinerError,
    extract_grobid_chunk,
    extract_pdfminer_chunk,
    orchestrate_extraction,
    wait_for_grobid,
)


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

    monotonic_values = iter([0.0, 0.0, 2.0])

    def _fake_monotonic():
        return next(monotonic_values, 2.0)

    monkeypatch.setattr("docdown.stages.extract.requests.get", _fake_get)
    monkeypatch.setattr("docdown.stages.extract.time.monotonic", _fake_monotonic)
    monkeypatch.setattr("docdown.stages.extract.time.sleep", lambda *_: None)

    with pytest.raises(GrobidError, match="did not become ready"):
        wait_for_grobid("http://localhost:8070", max_wait=1, poll_interval=1)


def test_wait_for_grobid_rejects_negative_max_wait():
    with pytest.raises(GrobidError, match="max_wait must be >= 0"):
        wait_for_grobid("http://localhost:8070", max_wait=-1)


def test_wait_for_grobid_rejects_non_positive_poll_interval():
    with pytest.raises(GrobidError, match="poll_interval must be > 0"):
        wait_for_grobid("http://localhost:8070", poll_interval=0)


def test_wait_for_grobid_rejects_non_positive_request_timeout():
    with pytest.raises(GrobidError, match="request_timeout must be > 0"):
        wait_for_grobid("http://localhost:8070", request_timeout=0)


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

    assert seen_timeouts == [120, 240, 120]
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


def test_extract_grobid_chunk_rejects_non_positive_timeout(tmp_path):
    chunk = tmp_path / "chunk-0001.pdf"
    output = tmp_path / "chunk-0001.xml"
    chunk.write_bytes(b"%PDF-1.4\n")

    with pytest.raises(GrobidError, match="timeout must be > 0"):
        extract_grobid_chunk(chunk, output, "http://localhost:8070", timeout=0)


def test_extract_grobid_chunk_rejects_negative_503_retries(tmp_path):
    chunk = tmp_path / "chunk-0001.pdf"
    output = tmp_path / "chunk-0001.xml"
    chunk.write_bytes(b"%PDF-1.4\n")

    with pytest.raises(GrobidError, match="retries_on_503 must be >= 0"):
        extract_grobid_chunk(chunk, output, "http://localhost:8070", retries_on_503=-1)


def test_extract_grobid_chunk_rejects_negative_backoff_base_seconds(tmp_path):
    chunk = tmp_path / "chunk-0001.pdf"
    output = tmp_path / "chunk-0001.xml"
    chunk.write_bytes(b"%PDF-1.4\n")

    with pytest.raises(GrobidError, match="backoff_base_seconds must be >= 0"):
        extract_grobid_chunk(chunk, output, "http://localhost:8070", backoff_base_seconds=-1)


def test_extract_pdfminer_chunk_writes_text_and_logs_time(tmp_path, monkeypatch, caplog):
    chunk = tmp_path / "chunk-0001.pdf"
    output = tmp_path / "extracted" / "chunk-0001.txt"
    chunk.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(
        "docdown.stages.extract.pdfminer_extract_text",
        lambda path: "line 1\nline 2\n",
    )
    test_logger = logging.getLogger("tests.extract.pdfminer")

    with caplog.at_level(logging.INFO, logger="tests.extract.pdfminer"):
        result = extract_pdfminer_chunk(chunk, output, logger=test_logger)

    assert result == output
    assert output.read_text(encoding="utf-8") == "line 1\nline 2\n"
    assert "pdfminer extraction complete" in caplog.text


def test_extract_pdfminer_chunk_rejects_missing_chunk_file(tmp_path):
    missing_chunk = tmp_path / "chunk-0001.pdf"
    output = tmp_path / "chunk-0001.txt"

    with pytest.raises(PdfMinerError, match=r"Chunk PDF not found: .*chunk-0001\.pdf"):
        extract_pdfminer_chunk(missing_chunk, output)


def test_orchestrate_extraction_all_succeed_with_grobid(tmp_path, monkeypatch, caplog):
    chunks = [tmp_path / "chunk-0001.pdf", tmp_path / "chunk-0002.pdf"]
    out_dir = tmp_path / "extracted"

    monkeypatch.setattr("docdown.stages.extract.wait_for_grobid", lambda *args, **kwargs: None)
    monkeypatch.setattr("docdown.stages.extract.extract_grobid_chunk", lambda chunk, output, *args, **kwargs: output)

    test_logger = logging.getLogger("tests.extract.orchestration")
    with caplog.at_level(logging.INFO, logger="tests.extract.orchestration"):
        results = orchestrate_extraction(
            chunks,
            out_dir,
            extractor="grobid",
            fallback_extractor="pdfminer",
            logger=test_logger,
        )

    assert results == [
        ExtractionResult(1, True, ExtractorUsed.GROBID, out_dir / "chunk-0001.xml", None),
        ExtractionResult(2, True, ExtractorUsed.GROBID, out_dir / "chunk-0002.xml", None),
    ]
    assert "Extraction summary: 2 succeeded (grobid), 0 succeeded (pdfminer), 0 failed" in caplog.text


def test_orchestrate_extraction_partial_failure_falls_back_per_chunk(tmp_path, monkeypatch):
    chunks = [tmp_path / "chunk-0001.pdf", tmp_path / "chunk-0002.pdf"]
    out_dir = tmp_path / "extracted"

    monkeypatch.setattr("docdown.stages.extract.wait_for_grobid", lambda *args, **kwargs: None)

    def _fake_grobid(chunk, output, grobid_url, **kwargs):
        if chunk.name == "chunk-0001.pdf":
            raise GrobidError("primary failed")
        return output

    monkeypatch.setattr("docdown.stages.extract.extract_grobid_chunk", _fake_grobid)
    monkeypatch.setattr("docdown.stages.extract.extract_pdfminer_chunk", lambda chunk, output, **kwargs: output)

    results = orchestrate_extraction(
        chunks,
        out_dir,
        extractor="grobid",
        fallback_extractor="pdfminer",
    )

    assert [result.extractor for result in results] == [ExtractorUsed.PDFMINER, ExtractorUsed.GROBID]
    assert all(result.success for result in results)
    assert results[0].output_path == out_dir / "chunk-0001.txt"
    assert results[1].output_path == out_dir / "chunk-0002.xml"


def test_orchestrate_extraction_when_grobid_down_skips_per_chunk_grobid(tmp_path, monkeypatch):
    chunks = [tmp_path / "chunk-0001.pdf", tmp_path / "chunk-0002.pdf"]
    out_dir = tmp_path / "extracted"

    monkeypatch.setattr(
        "docdown.stages.extract.wait_for_grobid",
        lambda *args, **kwargs: (_ for _ in ()).throw(GrobidError("unreachable")),
    )

    grobid_calls = {"count": 0}

    def _never_called(*args, **kwargs):
        grobid_calls["count"] += 1
        raise AssertionError("extract_grobid_chunk should not be called when GROBID is down")

    monkeypatch.setattr("docdown.stages.extract.extract_grobid_chunk", _never_called)
    monkeypatch.setattr("docdown.stages.extract.extract_pdfminer_chunk", lambda chunk, output, **kwargs: output)

    results = orchestrate_extraction(
        chunks,
        out_dir,
        extractor="grobid",
        fallback_extractor="pdfminer",
    )

    assert grobid_calls["count"] == 0
    assert [result.extractor for result in results] == [ExtractorUsed.PDFMINER, ExtractorUsed.PDFMINER]
    assert all(result.success for result in results)


def test_orchestrate_extraction_when_grobid_down_and_used_as_fallback_skips_calls(tmp_path, monkeypatch):
    chunks = [tmp_path / "chunk-0001.pdf"]
    out_dir = tmp_path / "extracted"

    monkeypatch.setattr(
        "docdown.stages.extract.wait_for_grobid",
        lambda *args, **kwargs: (_ for _ in ()).throw(GrobidError("unreachable")),
    )
    monkeypatch.setattr(
        "docdown.stages.extract.extract_pdfminer_chunk",
        lambda *args, **kwargs: (_ for _ in ()).throw(PdfMinerError("primary failed")),
    )

    grobid_calls = {"count": 0}

    def _never_called(*args, **kwargs):
        grobid_calls["count"] += 1
        raise AssertionError("extract_grobid_chunk should not be called when GROBID is down")

    monkeypatch.setattr("docdown.stages.extract.extract_grobid_chunk", _never_called)

    results = orchestrate_extraction(
        chunks,
        out_dir,
        extractor="pdfminer",
        fallback_extractor="grobid",
    )

    assert grobid_calls["count"] == 0
    assert len(results) == 1
    assert results[0].success is False
    assert "GROBID unavailable for fallback extraction" in (results[0].error or "")


def test_orchestrate_extraction_when_both_extractors_are_grobid_and_down_fails_without_calls(tmp_path, monkeypatch):
    chunks = [tmp_path / "chunk-0001.pdf", tmp_path / "chunk-0002.pdf"]
    out_dir = tmp_path / "extracted"

    monkeypatch.setattr(
        "docdown.stages.extract.wait_for_grobid",
        lambda *args, **kwargs: (_ for _ in ()).throw(GrobidError("unreachable")),
    )

    grobid_calls = {"count": 0}

    def _never_called(*args, **kwargs):
        grobid_calls["count"] += 1
        raise AssertionError("extract_grobid_chunk should not be called when GROBID is down")

    monkeypatch.setattr("docdown.stages.extract.extract_grobid_chunk", _never_called)

    results = orchestrate_extraction(
        chunks,
        out_dir,
        extractor="grobid",
        fallback_extractor="grobid",
    )

    assert grobid_calls["count"] == 0
    assert len(results) == 2
    assert all(not result.success for result in results)
    assert all("no non-GROBID extractor configured" in (result.error or "") for result in results)


def test_orchestrate_extraction_all_fail_returns_failed_results(tmp_path, monkeypatch):
    chunks = [tmp_path / "chunk-0001.pdf", tmp_path / "chunk-0002.pdf"]
    out_dir = tmp_path / "extracted"

    monkeypatch.setattr("docdown.stages.extract.wait_for_grobid", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "docdown.stages.extract.extract_grobid_chunk",
        lambda *args, **kwargs: (_ for _ in ()).throw(GrobidError("grobid failed")),
    )
    monkeypatch.setattr(
        "docdown.stages.extract.extract_pdfminer_chunk",
        lambda *args, **kwargs: (_ for _ in ()).throw(PdfMinerError("pdfminer failed")),
    )

    results = orchestrate_extraction(
        chunks,
        out_dir,
        extractor="grobid",
        fallback_extractor="pdfminer",
    )

    assert len(results) == 2
    assert all(not result.success for result in results)
    assert all(result.extractor is None for result in results)
    assert all(result.output_path is None for result in results)
    assert all(result.error == "pdfminer failed" for result in results)


def test_orchestrate_extraction_continues_after_primary_oserror(tmp_path, monkeypatch):
    chunks = [tmp_path / "chunk-0001.pdf", tmp_path / "chunk-0002.pdf"]
    out_dir = tmp_path / "extracted"

    monkeypatch.setattr("docdown.stages.extract.wait_for_grobid", lambda *args, **kwargs: None)

    def _fake_grobid(chunk, output, grobid_url, **kwargs):
        if chunk.name == "chunk-0001.pdf":
            raise OSError("disk write failed")
        return output

    monkeypatch.setattr("docdown.stages.extract.extract_grobid_chunk", _fake_grobid)
    monkeypatch.setattr("docdown.stages.extract.extract_pdfminer_chunk", lambda chunk, output, **kwargs: output)

    results = orchestrate_extraction(
        chunks,
        out_dir,
        extractor="grobid",
        fallback_extractor="pdfminer",
    )

    assert len(results) == 2
    assert results[0] == ExtractionResult(1, True, ExtractorUsed.PDFMINER, out_dir / "chunk-0001.txt", None)
    assert results[1] == ExtractionResult(2, True, ExtractorUsed.GROBID, out_dir / "chunk-0002.xml", None)


def test_orchestrate_extraction_invalid_chunk_name_does_not_block_others(tmp_path, monkeypatch):
    chunks = [tmp_path / "bad-name.pdf", tmp_path / "chunk-0002.pdf"]
    out_dir = tmp_path / "extracted"

    monkeypatch.setattr("docdown.stages.extract.wait_for_grobid", lambda *args, **kwargs: None)
    monkeypatch.setattr("docdown.stages.extract.extract_grobid_chunk", lambda chunk, output, *args, **kwargs: output)

    results = orchestrate_extraction(
        chunks,
        out_dir,
        extractor="grobid",
        fallback_extractor="pdfminer",
    )

    assert len(results) == 2
    assert results[0].success is False
    assert results[0].chunk_number == 0
    assert results[0].extractor is None
    assert results[0].output_path is None
    assert "Chunk filename must match" in (results[0].error or "")

    assert results[1] == ExtractionResult(2, True, ExtractorUsed.GROBID, out_dir / "chunk-0002.xml", None)


def test_orchestrate_extraction_rejects_non_padded_chunk_number(tmp_path, monkeypatch):
    chunks = [tmp_path / "chunk-1.pdf", tmp_path / "chunk-0002.pdf"]
    out_dir = tmp_path / "extracted"

    monkeypatch.setattr("docdown.stages.extract.wait_for_grobid", lambda *args, **kwargs: None)
    monkeypatch.setattr("docdown.stages.extract.extract_grobid_chunk", lambda chunk, output, *args, **kwargs: output)

    results = orchestrate_extraction(
        chunks,
        out_dir,
        extractor="grobid",
        fallback_extractor="pdfminer",
    )

    assert len(results) == 2
    assert results[0].success is False
    assert results[0].chunk_number == 0
    assert "chunk-NNNN.pdf" in (results[0].error or "")
    assert results[1] == ExtractionResult(2, True, ExtractorUsed.GROBID, out_dir / "chunk-0002.xml", None)


def test_orchestrate_extraction_rejects_chunk_zero_filename(tmp_path, monkeypatch):
    chunks = [tmp_path / "chunk-0000.pdf", tmp_path / "chunk-0002.pdf"]
    out_dir = tmp_path / "extracted"

    monkeypatch.setattr("docdown.stages.extract.wait_for_grobid", lambda *args, **kwargs: None)
    monkeypatch.setattr("docdown.stages.extract.extract_grobid_chunk", lambda chunk, output, *args, **kwargs: output)

    results = orchestrate_extraction(
        chunks,
        out_dir,
        extractor="grobid",
        fallback_extractor="pdfminer",
    )

    assert len(results) == 2
    assert results[0].success is False
    assert results[0].chunk_number == 0
    assert "chunk number >= 0001" in (results[0].error or "")
    assert results[1] == ExtractionResult(2, True, ExtractorUsed.GROBID, out_dir / "chunk-0002.xml", None)


def test_extract_pdfminer_chunk_rejects_empty_output(tmp_path, monkeypatch):
    chunk = tmp_path / "chunk-0001.pdf"
    output = tmp_path / "chunk-0001.txt"
    chunk.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr("docdown.stages.extract.pdfminer_extract_text", lambda path: "   \n\t")

    with pytest.raises(PdfMinerError, match="produced empty output"):
        extract_pdfminer_chunk(chunk, output)


def test_extract_pdfminer_chunk_wraps_extraction_errors(tmp_path, monkeypatch):
    chunk = tmp_path / "chunk-0001.pdf"
    output = tmp_path / "chunk-0001.txt"
    chunk.write_bytes(b"%PDF-1.4\n")

    def _raise_error(_path):
        raise UnicodeError("codec boom")

    monkeypatch.setattr("docdown.stages.extract.pdfminer_extract_text", _raise_error)

    with pytest.raises(PdfMinerError, match="pdfminer extraction failed"):
        extract_pdfminer_chunk(chunk, output)


@pytest.mark.integration
def test_extract_grobid_chunk_integration_real_service(tmp_path):
    if os.environ.get("RUN_GROBID_INTEGRATION") != "1":
        pytest.skip("Set RUN_GROBID_INTEGRATION=1 to run GROBID container integration test")

    fitz = pytest.importorskip("fitz")
    chunk = tmp_path / "chunk-0001.pdf"
    output = tmp_path / "chunk-0001.xml"

    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((72, 72), "DocDown integration test")
        doc.save(chunk)

    wait_for_grobid("http://localhost:8070", max_wait=60)
    result = extract_grobid_chunk(chunk, output, "http://localhost:8070", timeout=120)

    assert result.exists()
    assert "<TEI" in result.read_text(encoding="utf-8")
