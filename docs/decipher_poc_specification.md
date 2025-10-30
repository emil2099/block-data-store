# Decipher AI – Blocks Data Model Proof of Concept (POC) Specification

## 1. Purpose

Validate the viability of the block-based data model through an end-to-end implementation that spans ingestion, persistence, querying, rendering, and basic UI interaction. This POC establishes architectural foundations and validates performance, scalability assumptions, and developer experience.

This POC explicitly adheres to the layered architecture defined in the main specification: **Model Layer (Pydantic)** → **Repository Layer (SQLAlchemy abstraction)** → **Document Store Layer (business orchestration)** → **Renderer Layer (pluggable strategies for AI/UI)**.

---

## 2. Objectives

- Demonstrate full lifecycle: **Markdown → Parser → ORM/Repository (SQLite & Postgres) → Pydantic Models → Renderer → UI**.
- Implement **canonical block hierarchy** with selected block subclasses.
- Validate **secondary trees** via `page_group` + `synced` blocks.
- Implement **filtering** across structure and metadata.
- Provide **NiceGUI frontend** and **Jupyter notebook demo**.
- Establish **pytest-based test suite**, including performance tests.

---

## 3. In Scope

### Core Features

- Block schema with subclasses: `document`, `section`, `paragraph` (optional: `dataset`, `record`).
- Single canonical hierarchy with parent-owned ordering.
- Secondary grouping using `page_group` and `synced` block references (non-canonical trees).
- Parser to convert simplified Markdown into Blocks.
- ORM + Repository abstraction supporting both **SQLite & Postgres**.
- Recursive and non-recursive data fetching (`depth=0/1/all`) managed by the Document Store.
- Filtering aligned to the main spec using `where` (structural filters) and `filter` (property/metadata filters with nested JSON support).
- Renderer Layer implemented via pluggable strategies (e.g., MarkdownRenderer for AI, HtmlRenderer for UI). to Markdown & minimal HTML.

### Demonstrations

- **NiceGUI app**:
  - List documents
  - View hierarchical tree
  - Apply filters
  - Render block content
  - Edit metadata/properties
- **Jupyter notebook**:
  - Run end-to-end flows
  - Visualise blocks
  - Measure timings and query counts

### Quality & Testing

- Full **pytest suite**:
  - Structural integrity
  - Ordering & concurrency (version safety)
  - Filtering semantics
  - Secondary tree resolution
  - Performance benchmarks

---

## 4. Out of Scope

- CLI utilities
- Relationships and graph queries
- Authentication or multi-user logic
- Vector database integration
- Rich UX or production UI polish

---

## 5. Deliverables

| Deliverable | Description                                       |
| ----------- | ------------------------------------------------- |
| Data Model  | Pydantic models with subclasses and resolvers     |
| Parser      | Markdown → Block instances                        |
| DB Layer    | SQLAlchemy ORM + unified repository interface     |
| Filtering   | Structural + nested property filters              |
| Renderer    | Markdown + minimal HTML output functions          |
| NiceGUI App | Thin interface to browse, render, and edit blocks |
| Notebook    | End-to-end demonstration & performance tests      |
| Test Suite  | Pytest covering correctness and performance       |

---

## 6. Success Criteria

- A Markdown file can be parsed, persisted, queried, rendered, and viewed in UI.
- SQLite and Postgres produce identical functional results.
- Filtering returns correct subsets, including nested property queries.
- Secondary tree renders canonical content correctly.
- Performance metrics are recorded and meet acceptable baseline.
- All critical components covered by automated tests.

---

## 7. Next Steps

1. Implement minimal schema & repository.
2. Create core Block classes and parser.
3. Implement end-to-end ingestion and rendering.
4. Add filtering and secondary tree logic.
5. Build NiceGUI demo and notebook.
6. Finalise tests and run benchmarks.

