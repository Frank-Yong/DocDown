"""CLI entry point for DocDown."""

import click


@click.command()
@click.argument("input_pdf", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--config", "-c", type=click.Path(), default=None, help="Path to docdown.yaml")
@click.option("--workdir", "-o", type=click.Path(), default="./output", help="Working directory for artifacts")
def main(input_pdf, config, workdir):
    """Convert a PDF to Markdown."""
    click.echo(f"DocDown v{_version()}")
    click.echo(f"Input:   {input_pdf}")
    click.echo(f"Workdir: {workdir}")


def _version():
    from docdown import __version__
    return __version__

