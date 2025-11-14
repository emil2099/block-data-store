# **Azure Document Intelligence Parser Design**

Version: 0.1  
Status: Draft

## **1\. Purpose**

Define how we integrate Microsoft Azure Document Intelligence (DI) as an optional parser that converts PDFs into our block model while keeping the core package lightweight. The design captures today's requirement (Markdown-mode extraction) and anticipates future needs (images, multi-modal chunks, alternative providers) without introducing new core abstractions.

## **2\. Goals & Non-Goals**

**Goals**
1. Keep Markdown parser as the only mandatory dependency; add Azure DI behind an optional install extra.
2. Produce only blocks, with a single top-level `Document` root, consistent with existing parsers and store/renderer integration.
3. When page information is available, construct page group blocks using existing types and tag content blocks via `properties.groups` (no new result objects, no secondary data structures outside the block graph).
4. Support deterministic, offline tests plus opt-in integration tests that call the Azure API using developer-provided credentials.
5. Provide fixtures (sample PDF + per-page Markdown) so we can validate parser behavior without hitting Azure.

**Non-Goals**
1. Implement binary/image extraction in v1 (but keep hooks open).
2. Support multiple provider backends simultaneously—Docling etc. will follow the same extension pattern but are out of scope here.

## **3\. High-Level Architecture**

```
PDF bytes ──► Azure DI (markdown mode)
            │
            └─► (optionally) page-level metadata
                       │
                       ▼
        AzureDiParser (optional extra)
            │
            └─► list[Block] with one Document root, canonical content blocks, and page grouping blocks
```

### 3.1 Parser Contract (No New Types)
- Match current architecture: parsers return `list[Block]` where index 0 is the `Document` root.
- The Azure DI parser MUST build the canonical content using our existing Markdown parser and append additional group blocks under the same `root_id`.
- Any diagnostics or raw DI payloads are optional and, if needed later, can be attached as `metadata` on relevant blocks (not via a new return type).

### 3.2 Optional Dependency Wiring
- Package exposes `extras_require={"azure_di": ["azure-ai-formrecognizer>=...","python-dotenv>=..."]}`.
- Import guards in `block_data_store/parser/azure_di.py`; raising a clear `ImportError` with guidance when the extra is missing.
- Parser registration happens lazily (e.g., `register_parser("azure_di", AzureDiParser)` in module import guard).

## **4\. Page Group Modeling**

This design extends the "inverted tags" approach from `decipher_block_grouping_model.md`.

1. **Group Anchors**
   - Use existing types: `GroupIndexBlock(group_index_type="page")` under the document root; each physical page becomes a `PageGroupBlock` child (ordered as encountered).
   - Future chunking strategies can add a separate `GroupIndexBlock(group_index_type="chunk")` if/when needed. We are not assuming any DI-specific chunk shape now.

2. **Content Tagging**
   - The parser uses the existing `groups: list[UUID]` property on content blocks (e.g., Heading, Paragraph, List Items, Table, Quote, Code, Html) to tag membership in page groups.
   - If a single content block spans multiple pages, it carries multiple page IDs. We are not specifying how the mapping is derived; that depends on DI metadata reviewed at implementation time.

3. **Secondary Tree (Within Block Graph)**
   - Page grouping blocks are regular blocks in the same graph (same `root_id`). They do not parent canonical content; they only anchor ordering and metadata for pages.
   - We only commit to `page_number` for now. Additional attributes (e.g., coordinates, spans, file references) can be added later if required, as properties or metadata.

## **5\. Testing Strategy**

### 5.1 Fast Suite (default `pytest`)
- Add `tests/samples/pdf/{two_page.pdf, docid-page-01.md, docid-page-02.md}`.
- Create fixtures that load the expected per-page Markdown and compare it to the parser’s secondary tree rendering (without any API calls).
- Validate:
  - Canonical Markdown round-trip still passes via existing renderer.
  - Page grouping metadata aligns with sample expectations.

### 5.2 Integration Suite (opt-in)
- Mark tests hitting Azure with `@pytest.mark.azure_di`.
- Require explicit invocation (`pytest -m azure_di --env-file .env.azure`).
- Use `python-dotenv` (loaded in fixture) so credentials come from `AZURE_DI_ENDPOINT`, `AZURE_DI_KEY`, etc.
- Tests assert live Azure responses match stored Markdown/metadata to detect regressions.

### 5.3 CI Considerations
- Default CI runs skip Azure tests automatically.
- Provide documentation snippet showing how to run integration tests locally and in gated pipelines (e.g., set `RUN_AZURE_DI_TESTS=1`).

## **6\. Configuration & Secrets**

- Configuration object (`AzureDiConfig`) holds endpoint, key, API version, model selection (markdown mode).
- Load order:
  1. Direct kwargs (explicit in code/tests).
  2. Environment variables.
  3. `.env` files (optional helper for dev).

## **7\. Future Extensions**

| Area | Potential Change | Notes |
| --- | --- | --- |
| Images | Add optional attachment blocks referencing blob storage or inline base64 data. | Requires renderer updates. |
| Alternate Providers | Reuse parser pattern; place providers under separate extras and return plain `list[Block]`. | Ensure shared fixtures where possible. |
| Chunking Strategies | Allow configurable chunk builders (page-based vs. semantic). | Could emit multiple grouping indexes per document. |

## **8\. Open Questions**

1. **Pagination fidelity:** Do we capture bounding boxes now, or defer until visual renderers need them?
2. **Raw payloads:** Do we persist full DI JSON as block metadata or external artifact?
3. **Error handling:** On partial failures, do we save anything or abort the whole parse?
4. **Versioning:** How do we record parser/DI model versions (e.g., as document/root metadata)?

These questions will be resolved during implementation planning; this doc serves as the guiding reference for scope and architecture.  
