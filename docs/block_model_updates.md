# Block Model Refresh Checklist

This checklist maps each block type from `docs/decipher_block_specification.md` to the current implementation so we can track progress while updating the `block_data_store.models.blocks` package.

| Block Type | Spec Section | Current Implementation | Needed Changes |
| --- | --- | --- | --- |
| workspace | §6 WorkspaceBlock | Not implemented | Likely aligns with `workspace_id` metadata; confirm if an explicit block type is still required. |
| collection | §6 CollectionBlock | Missing | Add enum value + class with required `title`. |
| document | §6 DocumentBlock | Exists (missing `category` property) | Extend `DocumentProps` with optional `category`. |
| dataset | §6 DatasetBlock | Exists (property names differ) | Rename properties to `title`, `schema`, `category`; ensure schema validation. |
| derived_content_container | §6 DerivedContentContainerBlock | Missing | Add structural block with required `category`. |
| paragraph | §7 ParagraphBlock | Exists | Add `groups: tuple[UUID, ...] = ()` property + enforce `plain_text`. |
| bulleted_list_item | §7 BulletedListItemBlock | Exists | Same `groups` property + `plain_text` expectation. |
| numbered_list_item | §7 NumberedListItemBlock | Exists | Same as above. |
| heading | §7 HeadingBlock | Exists | Add `groups` + validate `level`. |
| quote | §7 QuoteBlock | Missing | Structural container with optional `groups`. |
| code | §7 CodeBlock | Missing | Add `language`, `groups`. |
| table | §7 TableBlock | Missing | Require `content.object`. |
| html | §7 HtmlBlock | Missing | Raw HTML carrier with `plain_text`. |
| object | §7 ObjectBlock | Missing | Require `content.object`, optional `category` + `groups`. |
| record | §8 RecordBlock | Exists | Add `groups` + enforce `content.data`. |
| group_index | §9 GroupIndexBlock | Missing | Structural root w/ `group_index_type`. |
| page_group | §9 PageGroupBlock | Exists (props just `title`) | Replace with required `page_number`. |
| chunk_group | §9 ChunkGroupBlock | Exists (empty props) | Keep empty but ensure `groups` not used. |
| unsupported | §10 UnsupportedBlock | Missing | Simple passthrough block.

Additional global needs:

- `BlockType` enum, `AnyBlock`, and `BLOCK_CLASS_MAP`/`PROPERTIES_CLASS_MAP` must include all of the above.
- `Content` model should expose `plain_text`, `object`, `data` keys per §3.1 (handled later alongside repo updates).
- Introduce reusable `GroupsMixin` property base so we don’t repeat tuple typing across blocks.
- Default `children_ids`/`groups` to tuples for immutability and to satisfy Pydantic frozen models.
