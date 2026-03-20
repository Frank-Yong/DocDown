"""DocDown — PDF-to-Markdown conversion pipeline."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("docdown")
except PackageNotFoundError:
    __version__ = "0.0.0"
