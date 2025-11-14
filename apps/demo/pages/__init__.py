"""Register NiceGUI pages by importing submodules."""

from . import home, documents, pdf_pages, tree, datasets  # noqa: F401

__all__ = ["home", "documents", "pdf_pages", "tree", "datasets"]

