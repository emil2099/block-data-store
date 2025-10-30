## Virtual environment
We are using python virtual environment installed in .venv directory. Make sure to use that prior to running any scripts.

## Design specification
Overall solution design is stored in the documents under the following files:
- decipher_full_specification.md contains overall design and some technical details over individual components
- decipher_poc_specification.md contains scope boundary and objectives of the POC that we are working on here

Refer to these documents regularly to ensure we stay on track, and call out if we start deviating from them so we can confirm there are good reasons for it.

## Progress tracking
Progress on the POC is stored in docs/poc_wip.md. Use this before starting work on new requests to understand the current state of the build.

Keep updating poc_wip.md as you make the changes so that we're tracking progress.

## Simplicity First
- Prefer simple, straightforward solutions
- Avoid over-engineering
- Remove obsolete code rather than working around it
- Code should be self-explanatory

## Code quality
- The library being designed is foundational to a larger product. As part of POC, it is important to cleanly test core ideas without introducing unnecessary levels of abstraction and complexity. It is instrumental to keep everything as simple and elegant as possible.

## When Uncertain

- **Check online sources** for inspiration or verification rather than guessing
- **Search the codebase** for similar patterns before inventing new ones
- **Ask the user** by presenting options and trade-offs if strategy is unclear
- **Start broad, then narrow**: Explore with semantic search, then drill into specific files

## Unit testing
- Make sure to run unit tests and also review the tests themselves to ensure good coverage after every significant code change.
- Do not settle for 'easy' unit tests, make sure you're actually testing the solution

