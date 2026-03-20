"""Tests for configuration loading and validation."""

from dataclasses import FrozenInstanceError

import pytest

from docdown.config import ConfigError, load_config


def test_config_defaults_without_file():
    cfg = load_config()

    assert cfg.input is None
    assert str(cfg.workdir) == "output"
    assert cfg.chunk_size == 50
    assert cfg.parallel_workers == 4
    assert cfg.extractor == "grobid"
    assert cfg.fallback_extractor == "pdfminer"
    assert cfg.table_extraction is True
    assert cfg.llm_cleanup is False
    assert cfg.validation.min_output_ratio == 0.01
    assert cfg.validation.max_empty_chunks == 0

    with pytest.raises(FrozenInstanceError):
        cfg.chunk_size = 10  # type: ignore[misc]


def test_config_loads_from_yaml(tmp_path):
    pdf_path = tmp_path / "input.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    cfg_path = tmp_path / "docdown.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                f"input: {pdf_path}",
                "workdir: ./custom-out",
                "chunk_size: 25",
                "parallel_workers: 2",
                "extractor: pdfminer",
                "grobid_url: http://127.0.0.1:8070",
                "fallback_extractor: grobid",
                "table_extraction: false",
                "llm_cleanup: true",
                "llm_model: gpt-4o-mini",
                "validation:",
                "  min_output_ratio: 0.02",
                "  max_empty_chunks: 1",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_config(cfg_path)

    assert cfg.input == pdf_path
    assert str(cfg.workdir) == "custom-out"
    assert cfg.chunk_size == 25
    assert cfg.parallel_workers == 2
    assert cfg.extractor == "pdfminer"
    assert cfg.grobid_url == "http://127.0.0.1:8070"
    assert cfg.fallback_extractor == "grobid"
    assert cfg.table_extraction is False
    assert cfg.llm_cleanup is True
    assert cfg.llm_model == "gpt-4o-mini"
    assert cfg.validation.min_output_ratio == 0.02
    assert cfg.validation.max_empty_chunks == 1


def test_cli_overrides_config_values(tmp_path):
    cfg_path = tmp_path / "docdown.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "workdir: ./from-file",
                "chunk_size: 100",
                "parallel_workers: 8",
                "validation:",
                "  min_output_ratio: 0.05",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_config(
        config_path=cfg_path,
        cli_overrides={
            "workdir": "./from-cli",
            "chunk_size": 20,
            "parallel_workers": 3,
            "validation": {
                "min_output_ratio": 0.1,
            },
        },
    )

    assert str(cfg.workdir) == "from-cli"
    assert cfg.chunk_size == 20
    assert cfg.parallel_workers == 3
    assert cfg.validation.min_output_ratio == 0.1


def test_invalid_config_raises_clear_error():
    with pytest.raises(ConfigError, match="chunk_size must be greater than 0"):
        load_config(cli_overrides={"chunk_size": 0})

    with pytest.raises(ConfigError, match="extractor must be one of"):
        load_config(cli_overrides={"extractor": "invalid"})


def test_string_boolean_values_are_rejected(tmp_path):
    cfg_path = tmp_path / "docdown.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                'table_extraction: "false"',
                'llm_cleanup: "true"',
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="table_extraction must be a boolean"):
        load_config(cfg_path)


def test_config_path_must_be_a_file(tmp_path):
    config_dir = tmp_path / "config-dir"
    config_dir.mkdir()

    with pytest.raises(ConfigError, match="Config path is not a file"):
        load_config(config_dir)


def test_input_file_must_exist_when_provided(tmp_path):
    missing_pdf = tmp_path / "missing.pdf"

    with pytest.raises(ConfigError, match="input file not found"):
        load_config(cli_overrides={"input": str(missing_pdf)})


def test_input_must_be_a_file_when_provided(tmp_path):
    input_dir = tmp_path / "input-dir"
    input_dir.mkdir()

    with pytest.raises(ConfigError, match="input must be a file"):
        load_config(cli_overrides={"input": str(input_dir)})


def test_workdir_must_be_a_directory_when_existing_path_is_file(tmp_path):
    workdir_file = tmp_path / "not-a-directory"
    workdir_file.write_text("x", encoding="utf-8")

    with pytest.raises(ConfigError, match="workdir must be a directory"):
        load_config(cli_overrides={"workdir": str(workdir_file)})


def test_chunk_size_boolean_is_rejected(tmp_path):
    cfg_path = tmp_path / "docdown.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "chunk_size: true",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="chunk_size must be an integer, not a boolean"):
        load_config(cfg_path)


def test_min_output_ratio_boolean_is_rejected(tmp_path):
    cfg_path = tmp_path / "docdown.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "validation:",
                "  min_output_ratio: false",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="validation.min_output_ratio must be a number, not a boolean"):
        load_config(cfg_path)
