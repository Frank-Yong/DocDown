"""Configuration loading and validation for DocDown."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


_VALID_EXTRACTORS = {"grobid", "pdfminer"}


class ConfigError(ValueError):
    """Raised when configuration loading or validation fails."""


@dataclass(frozen=True)
class ValidationConfig:
    """Validation thresholds used by later pipeline stages."""

    min_output_ratio: float = 0.01
    max_empty_chunks: int = 0


@dataclass(frozen=True)
class Config:
    """Immutable runtime configuration."""

    input: Path | None = None
    workdir: Path = Path("./output")
    chunk_size: int = 50
    parallel_workers: int = 4
    extractor: str = "grobid"
    grobid_url: str = "http://localhost:8070"
    fallback_extractor: str = "pdfminer"
    table_extraction: bool = True
    llm_cleanup: bool = False
    llm_model: str | None = None
    validation: ValidationConfig = field(default_factory=ValidationConfig)


def load_config(config_path: str | Path | None = None, cli_overrides: dict[str, Any] | None = None) -> Config:
    """Load config using precedence: defaults -> YAML -> CLI overrides."""

    base_data: dict[str, Any] = _default_data()

    if config_path:
        file_data = _read_yaml_config(Path(config_path))
        _merge_config_data(base_data, file_data)

    if cli_overrides:
        _apply_cli_overrides(base_data, cli_overrides)

    return _build_and_validate(base_data)


def _default_data() -> dict[str, Any]:
    return {
        "input": None,
        "workdir": "./output",
        "chunk_size": 50,
        "parallel_workers": 4,
        "extractor": "grobid",
        "grobid_url": "http://localhost:8070",
        "fallback_extractor": "pdfminer",
        "table_extraction": True,
        "llm_cleanup": False,
        "llm_model": None,
        "validation": {
            "min_output_ratio": 0.01,
            "max_empty_chunks": 0,
        },
    }


def _read_yaml_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")
    if not config_path.is_file():
        raise ConfigError(f"Config path is not a file: {config_path}")

    try:
        raw_text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Could not read config file {config_path}: {exc}") from exc

    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in config file {config_path}: {exc}") from exc

    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError("Config file must contain a top-level mapping/object.")

    return raw


def _merge_config_data(base: dict[str, Any], incoming: dict[str, Any]) -> None:
    for key, value in incoming.items():
        if key not in base:
            raise ConfigError(f"Unknown configuration key: {key}")

        if key == "validation":
            if not isinstance(value, dict):
                raise ConfigError("The 'validation' section must be a mapping/object.")
            for v_key, v_value in value.items():
                if v_key not in base["validation"]:
                    raise ConfigError(f"Unknown validation key: validation.{v_key}")
                base["validation"][v_key] = v_value
        else:
            base[key] = value


def _apply_cli_overrides(base: dict[str, Any], overrides: dict[str, Any]) -> None:
    validation_overrides = overrides.get("validation")

    for key, value in overrides.items():
        if key == "validation":
            continue
        if key not in base:
            raise ConfigError(f"Unknown CLI override key: {key}")
        if value is not None:
            base[key] = value

    if validation_overrides is not None:
        if not isinstance(validation_overrides, dict):
            raise ConfigError("CLI override 'validation' must be a mapping/object.")
        for key, value in validation_overrides.items():
            if key not in base["validation"]:
                raise ConfigError(f"Unknown CLI validation override key: validation.{key}")
            if value is not None:
                base["validation"][key] = value


def _build_and_validate(data: dict[str, Any]) -> Config:
    try:
        validation_cfg = ValidationConfig(
            min_output_ratio=_require_float(data["validation"]["min_output_ratio"], "validation.min_output_ratio"),
            max_empty_chunks=_require_int(data["validation"]["max_empty_chunks"], "validation.max_empty_chunks"),
        )

        cfg = Config(
            input=Path(data["input"]) if data["input"] is not None else None,
            workdir=Path(data["workdir"]),
            chunk_size=_require_int(data["chunk_size"], "chunk_size"),
            parallel_workers=_require_int(data["parallel_workers"], "parallel_workers"),
            extractor=str(data["extractor"]),
            grobid_url=str(data["grobid_url"]),
            fallback_extractor=str(data["fallback_extractor"]),
            table_extraction=_require_bool(data["table_extraction"], "table_extraction"),
            llm_cleanup=_require_bool(data["llm_cleanup"], "llm_cleanup"),
            llm_model=str(data["llm_model"]) if data["llm_model"] is not None else None,
            validation=validation_cfg,
        )
    except ConfigError:
        raise
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid configuration value type: {exc}") from exc

    _validate_semantics(cfg)
    return cfg


def _validate_semantics(cfg: Config) -> None:
    if cfg.input is not None:
        if not cfg.input.exists():
            raise ConfigError(f"input file not found: {cfg.input}")
        if not cfg.input.is_file():
            raise ConfigError(f"input must be a file: {cfg.input}")
        try:
            with cfg.input.open("rb"):
                pass
        except OSError as exc:
            raise ConfigError(f"input file is not readable: {cfg.input}: {exc}") from exc

    if cfg.workdir.exists() and not cfg.workdir.is_dir():
        raise ConfigError(f"workdir must be a directory: {cfg.workdir}")

    if cfg.chunk_size <= 0:
        raise ConfigError("chunk_size must be greater than 0.")
    if cfg.parallel_workers < 1:
        raise ConfigError("parallel_workers must be at least 1.")
    if cfg.extractor not in _VALID_EXTRACTORS:
        raise ConfigError(f"extractor must be one of: {sorted(_VALID_EXTRACTORS)}")
    if cfg.fallback_extractor not in _VALID_EXTRACTORS:
        raise ConfigError(f"fallback_extractor must be one of: {sorted(_VALID_EXTRACTORS)}")
    if cfg.validation.min_output_ratio <= 0:
        raise ConfigError("validation.min_output_ratio must be greater than 0.")
    if cfg.validation.max_empty_chunks < 0:
        raise ConfigError("validation.max_empty_chunks must be at least 0.")


def _require_bool(value: Any, key: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ConfigError(f"{key} must be a boolean (true/false).")


def _require_int(value: Any, key: str) -> int:
    if isinstance(value, bool):
        raise ConfigError(f"{key} must be an integer, not a boolean.")
    return int(value)


def _require_float(value: Any, key: str) -> float:
    if isinstance(value, bool):
        raise ConfigError(f"{key} must be a number, not a boolean.")
    return float(value)

