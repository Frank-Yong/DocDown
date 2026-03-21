"""CLI entry point for DocDown."""

import click

from docdown.config import ConfigError, load_config
from docdown.utils.logging import configure_logging


@click.command()
@click.argument("input_pdf", required=False, type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--config", "-c", type=click.Path(), default=None, help="Path to docdown.yaml")
@click.option(
    "--workdir",
    "-o",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    help="Working directory for artifacts",
)
@click.option("--chunk-size", type=int, default=None, help="Pages per chunk")
@click.option("--parallel-workers", type=int, default=None, help="Max chunk workers")
@click.option("--extractor", type=click.Choice(["grobid", "pdfminer"]), default=None, help="Primary extractor")
@click.option(
    "--fallback-extractor",
    type=click.Choice(["grobid", "pdfminer"]),
    default=None,
    help="Fallback extractor",
)
@click.option("--grobid-url", type=str, default=None, help="GROBID service URL")
@click.option("--table-extraction/--no-table-extraction", default=None, help="Enable table extraction")
@click.option("--llm-cleanup/--no-llm-cleanup", default=None, help="Enable LLM cleanup pipeline")
@click.option("--llm-model", type=str, default=None, help="LLM model identifier")
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "WARN"], case_sensitive=False),
    default=None,
    help="Log verbosity level",
)
@click.option("--min-output-ratio", type=float, default=None, help="Validation minimum output ratio")
@click.option("--max-empty-chunks", type=int, default=None, help="Validation max empty chunks")
def main(
    input_pdf,
    config,
    workdir,
    chunk_size,
    parallel_workers,
    extractor,
    fallback_extractor,
    grobid_url,
    table_extraction,
    llm_cleanup,
    llm_model,
    log_level,
    min_output_ratio,
    max_empty_chunks,
):
    """Convert a PDF to Markdown."""

    cli_overrides = {
        "input": input_pdf,
        "workdir": workdir,
        "chunk_size": chunk_size,
        "parallel_workers": parallel_workers,
        "extractor": extractor,
        "fallback_extractor": fallback_extractor,
        "grobid_url": grobid_url,
        "table_extraction": table_extraction,
        "llm_cleanup": llm_cleanup,
        "llm_model": llm_model,
        "log_level": log_level,
        "validation": {
            "min_output_ratio": min_output_ratio,
            "max_empty_chunks": max_empty_chunks,
        },
    }

    try:
        cfg = load_config(config_path=config, cli_overrides=cli_overrides)
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    if cfg.input is None:
        raise click.ClickException("No input PDF provided. Pass INPUT_PDF or set 'input' in docdown.yaml.")

    logger = configure_logging(cfg.workdir, cfg.log_level)
    version_text = f"DocDown v{_version()}"
    input_text = f"Input:   {cfg.input}"
    workdir_text = f"Workdir: {cfg.workdir}"

    # Keep CLI summaries on stdout while also recording them in logs.
    click.echo(version_text)
    click.echo(input_text)
    click.echo(workdir_text)

    logger.info(version_text)
    logger.info(input_text)
    logger.info(workdir_text)


def _version():
    from docdown import __version__
    return __version__

