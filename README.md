# Block Data Store

Unified block-based content model with persistence, parsing, and rendering layers. Every document, section, paragraph, and dataset is represented as a typed block, making it easy to store, filter, and render structured content.

## Install (from GitHub)

```bash
pip install git+https://github.com/emil2099/block-data-store.git
```

Pin a tag or commit for reproducible installs, e.g.:

```bash
pip install "git+https://github.com/emil2099/block-data-store.git@v0.1.0"
```

## Quickstart

```python
from block_data_store.store import BlockDataStore

store = BlockDataStore(database_url="sqlite:///block_store.db")
store.create_all()
```

## Development

- Clone the repo and create a virtualenv in `.venv`
- Install dev deps: `pip install -r requirements.txt`
- Run tests: `pytest`

## Versioning

The package uses semantic versions. Current release: `0.1.0`.

## Release (GitHub)

1. Bump the version in `pyproject.toml` and `block_data_store/__init__.py`.
2. Commit the changes and tag: `git commit -am "chore: release v0.1.0" && git tag v0.1.0`.
3. Push the tag: `git push origin main --tags`.
4. Users can install the tagged release: `pip install "git+https://github.com/<owner>/block_data_store.git@v0.1.0"`.
