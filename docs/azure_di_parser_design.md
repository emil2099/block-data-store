# Azure Document Intelligence Parser Design

## **1. Purpose**

This document defines the design for integrating Microsoft Azure Document Intelligence (DI) as an optional parser. The goal is to convert source documents (like PDFs) into the Decipher Block model, correctly handling page information while keeping the core application lightweight and extensible.

## **2. Goals & Non-Goals**

### **Goals**

1. Keep the existing Markdown parser as the only mandatory dependency; add Azure DI behind an optional install extra (`extras_require`).
2. Produce a `list[Block]` with a single top-level `Document` root, consistent with the existing parser contract.
3. Provide an option to create page group blocks and tag content blocks with page membership, using the established "inverted tags" model from `decipher_block_grouping_model.md`.
4. Ensure the design is testable with both fast, offline fixtures and opt-in integration tests that call the live Azure API.

### **Non-Goals**

1. Implement binary or image extraction in this version.
2. Support multiple backend providers simultaneously; other providers can follow this same extension pattern in the future.

## **3. High-Level Architecture & Core Logic**

The parser will be exposed through a primary function that takes the source document and an optional flag to control the creation of page groups.

`parse(document_stream, *, create_page_groups: bool = True, ...)`

### **3.1. Logic for `create_page_groups=True` (Default Behavior)**

This mode generates a full block graph with page groupings. It follows a pragmatic **"Page-First"** model for simplicity and speed of implementation.

1. **Single API Call:** Make one call to the Azure DI service to retrieve the complete `AnalyzeResult` object for the entire document. This object contains both the full-document Markdown content and the metadata for each page, including character `spans`.
2. **Create Group Anchors:** Iterate through the `result.pages` list from the API response. For each page, create a `PageGroupBlock` and store its UUID in an in-memory map (e.g., `{page_number: page_uuid}`). These will all be children of a single `GroupIndexBlock`.
3. **Process Content Page by Page:** Loop through `result.pages` again. In each iteration:
a. Get the current page number and its corresponding `page_uuid` from the map.
b. Use the `page.spans` to **slice** the page-specific Markdown content out of the master `result.content` string.
c. Pass this page-specific Markdown snippet to the existing, unmodified Markdown-to-Block parser.
d. For **every block** returned by the parser for this page, add the current `page_uuid` to its `properties.groups` list.
4. **Consolidate and Return:** Collect the blocks from all pages into a single list, ensuring there is one `Document` root, and return the complete list.

### **3.2. Logic for `create_page_groups=False`**

This mode provides a faster, simpler parse when only the canonical content is needed.

1. **Single API Call:** Make one call to the Azure DI service to retrieve the `AnalyzeResult`.
2. **Extract Full Markdown:** Get the complete `result.content` string, which represents the entire document.
3. **Parse Entire Document:** Pass the full Markdown string to the existing Markdown-to-Block parser in a single pass.
4. **Return Blocks:** Return the resulting `list[Block]`. No `GroupIndexBlock`, `PageGroupBlock`, or `properties.groups` tags will be created.

## **4. Implementation Strategy & Trade-offs**

### **4.1. V1 Strategy: Pragmatic "Page-First" Model**

The initial implementation will use the "Page-First" model described in section 3.1. This approach is prioritized for its simplicity, as it leverages the existing Markdown parser without modification and avoids the complexity of character-level source mapping.

### **4.2. Acknowledged Trade-off: Split Blocks**

The primary trade-off of the "Page-First" model is that it will split semantic blocks that span a physical page break. For example, a single paragraph that starts on page one and ends on page two will be ingested as **two separate `ParagraphBlock`s**. The first will be tagged with page one, and the second with page two.

This is a conscious and acceptable trade-off for the initial version. The impact of this will be evaluated against real-world documents.

### **4.3. Future Evolution: "Canonical-First" Model**

The impact of the "split block" issue will be assessed with a test harness of representative documents. If the issue is found to be significant for downstream use cases (like AI chunking or semantic analysis), the parser may be evolved to a more robust **"Canonical-First"** model in a future iteration. This would involve using a parser capable of generating source maps (character offsets) to build a perfect canonical tree first, and then applying page tags in a second pass.

## **5. Caching Strategy**

To improve performance and reduce operational costs, a caching layer is strongly recommended.

- **What to Cache:** The serialized `AnalyzeResult` object returned from the Azure DI API call. Caching this raw output allows for re-parsing with updated internal logic without making another expensive API call.
- **Cache Key:** A deterministic hash (e.g., SHA-256) of the **source document's binary content**. This ensures that any change to the input document invalidates the cache.
- **Workflow:** Before calling the API, the parser should check the cache using the content hash. On a cache hit, it deserializes the stored `AnalyzeResult` and proceeds. On a miss, it calls the API and stores the new result in the cache before proceeding.

## **6. Page Group Modeling**

The design will adhere to the "inverted tags" approach from `decipher_block_grouping_model.md`.

- **Group Anchors:** A single `GroupIndexBlock(group_index_type="page")` will be created under the document root. Each physical page will be represented by a `PageGroupBlock` child of this index.
- **Content Tagging:** The `properties.groups: list[UUID]` field on content blocks will be populated with the UUIDs of the `PageGroupBlock`(s) they belong to.

## **7. Testing Strategy**

A two-tiered testing approach will be used:

1. **Fast Suite (Default):** Unit tests will use stored fixtures (e.g., a sample PDF and its expected per-page Markdown output) to validate the parser's block generation and tagging logic without making any live API calls.
2. **Integration Suite (Opt-in):** Tests marked with `@pytest.mark.azure_di` will make live calls to the Azure DI service. These tests will require developer-provided credentials (via environment variables) and will be skipped in default CI runs.

## **8. Configuration & Secrets**

A dedicated configuration object (e.g., `AzureDiConfig`) will manage settings. Credentials (`AZURE_DI_ENDPOINT`, `AZURE_DI_KEY`) will be loaded from environment variables or `.env` files, following standard practice.

## **9. Open Questions & Resolutions**

- **Handling Split Blocks:**
    - **Resolution:** For V1, the simpler "Page-First" model will be implemented, which splits blocks across page breaks. This is a known trade-off. The impact will be evaluated with real documents to determine if a more complex "Canonical-First" model is needed in the future.
- **Pagination Fidelity (Bounding Boxes):**
    - **Resolution:** Defer. Capturing bounding boxes is not required for the initial implementation. They can be added to block `metadata` in the future if a visual rendering use case emerges.
- **Raw API Payloads:**
    - **Resolution:** Do not persist by default. The full JSON payload from DI can be voluminous. The implementation may include a temporary, configurable option to log this payload or attach it to the root block's `metadata` for debugging purposes.
- **Error Handling:**
    - **Resolution:** Abort the entire parse on partial failures from the API to prevent data corruption.
- **Versioning:**
    - **Resolution:** The parser should record the DI model version used (e.g., `prebuilt-layout@2023-10-31-preview`) in the `metadata` field of the root `DocumentBlock` for traceability.