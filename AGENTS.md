## About this project

Block Data Store defines a unified block-based content model where every document, section, paragraph, and dataset is a typed block with canonical hierarchy, enabling structured storage, filtering, and rendering. It combines the model, persistence, parser, renderer, and orchestration layers with tooling (UI demo, scripts, tests) to showcase how content flows from source into AI-friendly views.

## Core Principles

### Think from First Principles

Don't settle for the first solution.
Question assumptions and think deeply about the true nature of the problem before implementing.

### Pair Programming Approach

We work together as pair programmers, switching seamlessly between driver and navigator:

- **Requirements first**: Verify requirements are correct before implementing, especially when writing/changing tests
- **Discuss strategy**: Present options and trade-offs when uncertain about approach
- **Step-by-step for large changes**: Break down significant refactorings and get confirmation at each step
- **Challenge assumptions**: If the user makes wrong assumptions or states untrue facts, correct them directly

### Simplicity First

- Prefer simple, straightforward solutions
- Avoid over-engineering
- Remove obsolete code rather than working around it
- Code should be self-explanatory

### Code quality

- The library being designed is foundational to a larger product. As part of POC, it is important to cleanly test core ideas without introducing unnecessary levels of abstraction and complexity. It is instrumental to keep everything as simple and elegant as possible. There is a high cost of added complexity or implicit assumptions

## Working with code base

### Virtual environment

We are using python virtual environment installed in .venv directory. Make sure to use that prior to running any scripts.

### Project structure

Core module
- `block_data_store/models/` - Typed Pydantic base + per-block subclasses forming the  data model
- `block_data_store/db/` - SQLAlchemy schema definitions and engine/session helpers
- `block_data_store/repositories/` - Data repository ersistence layer and structured filtering service
- `block_data_store/store/` - Document-store facade and factory wiring the layers together
- `block_data_store/parser/` - Specific parsers for different types of inputs like markdown and others
- `block_data_store/renderers/` - Renderer interfaces and implementations for turning blocks into text outputs

Non-Core Modules
- `docs/` - Architecture specifications
- `tests/` - Test suite
- `apps` - NiceGUI demo 
- `scripts/` - Operational non-prod helpers 
- `data/` - Sample datasets
- `notebooks/` - Demonstration and performance notebooks

### Design specification

Refer to provided documentation regularly to ensure we stay on track, and call out if we start deviating from them so we can confirm there are good reasons for it.

We don't care about sticking to the design 1-2-1 if there are good reasons to evolve it.

We don't care about backward compatibility - this is a new library so things can and should evolve rapidly if the changes are justified and bring overall clarity!

### When Uncertain

- **Check online sources** for inspiration or verification rather than guessing
- **Search the codebase** for similar patterns before inventing new ones
- **Ask the user** by presenting options and trade-offs if strategy is unclear
- **Start broad, then narrow**: Explore with semantic search, then drill into specific files

## Unit testing

- When making significant changes, make sure to run unit tests and also review the tests themselves to ensure good coverage after every significant code change.
- Do not settle for 'easy' unit tests, make sure you're actually testing the solution

