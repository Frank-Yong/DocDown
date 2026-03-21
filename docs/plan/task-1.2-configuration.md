# Task 1.2 — Configuration System

## Summary

Implement configuration loading from a YAML file and CLI flags, with sensible defaults for all parameters.

## Dependencies

- Task 1.1 (project structure)

## Acceptance Criteria

- [x] `docdown.yaml` schema is defined and documented.
- [x] Configuration loads from file path specified via `--config` CLI flag.
- [x] CLI flags override config file values.
- [x] All parameters have defaults (pipeline runs without a config file).
- [x] Invalid configuration produces a clear error message and exits.
- [x] Configuration object is immutable after loading.
- [x] Unit tests cover: defaults, file loading, CLI overrides, validation errors.

## Implementation Notes

### Configuration schema

```yaml
input: null                        # required
workdir: ./output
chunk_size: 50
parallel_workers: 4
extractor: grobid                  # grobid | pdfminer
grobid_url: http://localhost:8070
fallback_extractor: pdfminer
table_extraction: true
llm_cleanup: false
llm_model: null
validation:
  min_output_ratio: 0.01
  max_empty_chunks: 0
```

### Design

- Use a dataclass or Pydantic model for typed, validated config.
- Load order: defaults → YAML file → CLI flags.
- Validate `extractor` and `fallback_extractor` are valid choices.
- Validate `chunk_size` > 0, `parallel_workers` ≥ 1.

### Artifact Class Diagram

```mermaid
classDiagram
  class ConfigError {
    <<exception>>
  }

  class ValidationConfig {
    +float min_output_ratio
    +int max_empty_chunks
  }

  class Config {
    +Path? input
    +Path workdir
    +int chunk_size
    +int parallel_workers
    +str extractor
    +str grobid_url
    +str fallback_extractor
    +bool table_extraction
    +bool llm_cleanup
    +str? llm_model
    +ValidationConfig validation
  }

  class ConfigModule {
    <<module: docdown/config.py>>
    +load_config(config_path, cli_overrides) Config
    -_default_data() dict
    -_read_yaml_config(path) dict
    -_merge_config_data(base, incoming) None
    -_apply_cli_overrides(base, overrides) None
    -_build_and_validate(data) Config
    -_validate_semantics(cfg) None
    -_require_bool(value, key) bool
    -_require_int(value, key) int
    -_require_float(value, key) float
  }

  class CliMain {
    <<module: docdown/cli.py>>
    +main(input_pdf, config, workdir, ...) None
  }

  class DocdownYaml {
    <<file: docdown.yaml>>
    +runtime defaults/schema
  }

  class TestConfig {
    <<tests/test_config.py>>
    +default, file, override, validation tests
  }

  class TestCli {
    <<tests/test_cli.py>>
    +CLI wiring and option validation tests
  }

  ConfigModule ..> Config : builds/validates
  ConfigModule ..> ValidationConfig : builds
  ConfigModule ..> ConfigError : raises
  CliMain ..> ConfigModule : calls load_config
  DocdownYaml ..> ConfigModule : input source
  TestConfig ..> ConfigModule : verifies behavior
  TestCli ..> CliMain : verifies integration
  Config --> ValidationConfig : contains
```

## References

- [technical-design.md §4 — Configuration](../technical-design.md)
