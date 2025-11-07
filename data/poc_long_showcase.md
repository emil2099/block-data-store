# Iteration 1

# Systems Integration Handbook

Welcome to the systems integration handbook for the Decipher POC environment. This document is intentionally long to demonstrate tree depth, nested structures, and dataset handling.

## Objectives

1. Establish a consistent vocabulary for integration partners.
2. Showcase how multi-level headings, lists, and datasets are represented in the block data store.
3. Provide a reusable template that can be extended for production scenarios.

## Section 1 — Canonical Model Overview

### 1.1 Terminology

- **Canonical tree**: The primary hierarchy rooted at the document block.
- **Secondary tree**: Alternative perspectives composed with synced references.
- **Block**: Typed entity with properties, metadata, and optional content payloads.

### 1.2 Key Responsibilities

1. Persist every block with deterministic identifiers.
2. Maintain referential integrity across parent-child relationships.
3. Enable filtered projections over structure, metadata, and JSON content.

### 1.3 Supported Block Types

- Document
  - Heading
    - Paragraph
    - Bulleted list item
    - Numbered list item
- Dataset
  - Record

### 1.4 Operational Constraints

> Note: The POC parser intentionally limits supported Markdown features to a minimal but expressive subset.

## Section 2 — Integration Playbook

### 2.1 Ingestion Pipeline

```dataset:ingestion_flow
{
  "records": [
    {
      "step": "Parse markdown",
      "description": "Convert author-facing content into typed blocks."
    },
    {
      "step": "Normalize identifiers",
      "description": "Assign deterministic UUIDs for reproducible references."
    },
    {
      "step": "Persist",
      "description": "Store blocks via the repository layer using SQLAlchemy."
    }
  ]
}
```

#### 2.1.1 Data Validation Checklist

- Confirm every block has a parent except for the document root.
- Ensure dataset records include a JSON payload.
- Verify the tree is acyclic by construction.

#### 2.1.2 Error Handling

1. Reject malformed datasets early.
2. Surface descriptive validation errors to the caller.
3. Retain the raw Markdown payload to aid debugging.

### 2.2 Query Patterns

```dataset:query_patterns
{
  "records": [
    {
      "name": "Root scoped paragraphs",
      "where": {"type": "paragraph"},
      "root": {"title": "Systems Integration Handbook"}
    },
    {
      "name": "Headings under onboarding",
      "parent": {"title": "Onboarding Checklist"}
    },
    {
      "name": "Datasets tagged finance",
      "metadata": {"tags": ["finance", "risk"]}
    }
  ]
}
```

#### 2.2.1 Structural Filters

- Target block type, parent, or root identifiers.
- Combine multiple filters for precise slices.
- Limit result sets to maintain predictable UI latency.

#### 2.2.2 Semantic Filters

1. Use JSON path expressions (`properties.title`, `content.data.category`).
2. Apply boolean compositions to narrow results.
3. Support equality, containment, and membership comparisons.

### 2.3 Example Walkthrough

1. Select **Systems Integration Handbook** in the sidebar.
2. Expand the **Repository Filters** panel and set `Block type` to `paragraph`.
3. Add a parent constraint where `properties.title` contains `Checklist`.
4. Inspect the resulting blocks and confirm the hierarchy in the tree view.

## Section 3 — Onboarding Checklist

### 3.1 Pre-flight

- Confirm access to staging credentials.
- Sync feature toggles across environments.
- Review the latest architecture notes.

### 3.2 Day Zero Actions

1. Provision the integration service account.
2. Execute the base ingestion script on sample content.
3. Capture metrics for parser runtime and block counts.

### 3.3 Monitoring Grid

```dataset:monitoring_grid
{
  "records": [
    {
      "metric": "ingest_runtime_ms",
      "threshold": 250,
      "status": "pass"
    },
    {
      "metric": "blocks_created",
      "threshold": 400,
      "status": "observe"
    },
    {
      "metric": "dataset_records",
      "threshold": 120,
      "status": "pass"
    }
  ]
}
```

### 3.4 Nested Lists Demonstration

- Milestones
  - Kick-off meeting
    - Agenda drafted
    - Stakeholders invited
  - First sandbox sync
    1. Run seed scripts
    2. Validate dataset outputs
- Risks
  - Parser drift
  - Schema changes without migration

## Section 4 — Reference Notes

### 4.1 Frequently Asked Questions

1. **Can we ingest HTML?** No, transform to Markdown or use a custom renderer.
2. **How are synced blocks represented?** As references resolved in the DocumentStore layer.
3. **Is pagination supported?** Not in the POC; rely on filtered queries.

### 4.2 Future Enhancements

- Expand parser to support tables and callouts.
- Introduce HTML renderer variant.
- Add mutation APIs for secondary trees.

### 4.3 Revision History

```dataset:revision_history
{
  "records": [
    {
      "version": "v0.1",
      "summary": "Initial synthetic long-form document."
    },
    {
      "version": "v0.2",
      "summary": "Added monitoring dataset and nested list examples."
    }
  ]
}
```

### 4.4 Closing Thoughts

This synthetic handbook demonstrates a moderately deep block tree, multiple datasets, and combined list structures. Use it to validate query performance, renderer output, and UI responsiveness within the POC scope.



# Iteration 2

# Systems Integration Handbook

Welcome to the systems integration handbook for the Decipher POC environment. This document is intentionally long to demonstrate tree depth, nested structures, and dataset handling.

## Objectives

1. Establish a consistent vocabulary for integration partners.
2. Showcase how multi-level headings, lists, and datasets are represented in the block data store.
3. Provide a reusable template that can be extended for production scenarios.

## Section 1 — Canonical Model Overview

### 1.1 Terminology

- **Canonical tree**: The primary hierarchy rooted at the document block.
- **Secondary tree**: Alternative perspectives composed with synced references.
- **Block**: Typed entity with properties, metadata, and optional content payloads.

### 1.2 Key Responsibilities

1. Persist every block with deterministic identifiers.
2. Maintain referential integrity across parent-child relationships.
3. Enable filtered projections over structure, metadata, and JSON content.

### 1.3 Supported Block Types

- Document
  - Heading
    - Paragraph
    - Bulleted list item
    - Numbered list item
- Dataset
  - Record

### 1.4 Operational Constraints

> Note: The POC parser intentionally limits supported Markdown features to a minimal but expressive subset.

## Section 2 — Integration Playbook

### 2.1 Ingestion Pipeline

```dataset:ingestion_flow
{
  "records": [
    {
      "step": "Parse markdown",
      "description": "Convert author-facing content into typed blocks."
    },
    {
      "step": "Normalize identifiers",
      "description": "Assign deterministic UUIDs for reproducible references."
    },
    {
      "step": "Persist",
      "description": "Store blocks via the repository layer using SQLAlchemy."
    }
  ]
}
```

#### 2.1.1 Data Validation Checklist

- Confirm every block has a parent except for the document root.
- Ensure dataset records include a JSON payload.
- Verify the tree is acyclic by construction.

#### 2.1.2 Error Handling

1. Reject malformed datasets early.
2. Surface descriptive validation errors to the caller.
3. Retain the raw Markdown payload to aid debugging.

### 2.2 Query Patterns

```dataset:query_patterns
{
  "records": [
    {
      "name": "Root scoped paragraphs",
      "where": {"type": "paragraph"},
      "root": {"title": "Systems Integration Handbook"}
    },
    {
      "name": "Headings under onboarding",
      "parent": {"title": "Onboarding Checklist"}
    },
    {
      "name": "Datasets tagged finance",
      "metadata": {"tags": ["finance", "risk"]}
    }
  ]
}
```

#### 2.2.1 Structural Filters

- Target block type, parent, or root identifiers.
- Combine multiple filters for precise slices.
- Limit result sets to maintain predictable UI latency.

#### 2.2.2 Semantic Filters

1. Use JSON path expressions (`properties.title`, `content.data.category`).
2. Apply boolean compositions to narrow results.
3. Support equality, containment, and membership comparisons.

### 2.3 Example Walkthrough

1. Select **Systems Integration Handbook** in the sidebar.
2. Expand the **Repository Filters** panel and set `Block type` to `paragraph`.
3. Add a parent constraint where `properties.title` contains `Checklist`.
4. Inspect the resulting blocks and confirm the hierarchy in the tree view.

## Section 3 — Onboarding Checklist

### 3.1 Pre-flight

- Confirm access to staging credentials.
- Sync feature toggles across environments.
- Review the latest architecture notes.

### 3.2 Day Zero Actions

1. Provision the integration service account.
2. Execute the base ingestion script on sample content.
3. Capture metrics for parser runtime and block counts.

### 3.3 Monitoring Grid

```dataset:monitoring_grid
{
  "records": [
    {
      "metric": "ingest_runtime_ms",
      "threshold": 250,
      "status": "pass"
    },
    {
      "metric": "blocks_created",
      "threshold": 400,
      "status": "observe"
    },
    {
      "metric": "dataset_records",
      "threshold": 120,
      "status": "pass"
    }
  ]
}
```

### 3.4 Nested Lists Demonstration

- Milestones
  - Kick-off meeting
    - Agenda drafted
    - Stakeholders invited
  - First sandbox sync
    1. Run seed scripts
    2. Validate dataset outputs
- Risks
  - Parser drift
  - Schema changes without migration

## Section 4 — Reference Notes

### 4.1 Frequently Asked Questions

1. **Can we ingest HTML?** No, transform to Markdown or use a custom renderer.
2. **How are synced blocks represented?** As references resolved in the DocumentStore layer.
3. **Is pagination supported?** Not in the POC; rely on filtered queries.

### 4.2 Future Enhancements

- Expand parser to support tables and callouts.
- Introduce HTML renderer variant.
- Add mutation APIs for secondary trees.

### 4.3 Revision History

```dataset:revision_history
{
  "records": [
    {
      "version": "v0.1",
      "summary": "Initial synthetic long-form document."
    },
    {
      "version": "v0.2",
      "summary": "Added monitoring dataset and nested list examples."
    }
  ]
}
```

### 4.4 Closing Thoughts

This synthetic handbook demonstrates a moderately deep block tree, multiple datasets, and combined list structures. Use it to validate query performance, renderer output, and UI responsiveness within the POC scope.



# Iteration 3

# Systems Integration Handbook

Welcome to the systems integration handbook for the Decipher POC environment. This document is intentionally long to demonstrate tree depth, nested structures, and dataset handling.

## Objectives

1. Establish a consistent vocabulary for integration partners.
2. Showcase how multi-level headings, lists, and datasets are represented in the block data store.
3. Provide a reusable template that can be extended for production scenarios.

## Section 1 — Canonical Model Overview

### 1.1 Terminology

- **Canonical tree**: The primary hierarchy rooted at the document block.
- **Secondary tree**: Alternative perspectives composed with synced references.
- **Block**: Typed entity with properties, metadata, and optional content payloads.

### 1.2 Key Responsibilities

1. Persist every block with deterministic identifiers.
2. Maintain referential integrity across parent-child relationships.
3. Enable filtered projections over structure, metadata, and JSON content.

### 1.3 Supported Block Types

- Document
  - Heading
    - Paragraph
    - Bulleted list item
    - Numbered list item
- Dataset
  - Record

### 1.4 Operational Constraints

> Note: The POC parser intentionally limits supported Markdown features to a minimal but expressive subset.

## Section 2 — Integration Playbook

### 2.1 Ingestion Pipeline

```dataset:ingestion_flow
{
  "records": [
    {
      "step": "Parse markdown",
      "description": "Convert author-facing content into typed blocks."
    },
    {
      "step": "Normalize identifiers",
      "description": "Assign deterministic UUIDs for reproducible references."
    },
    {
      "step": "Persist",
      "description": "Store blocks via the repository layer using SQLAlchemy."
    }
  ]
}
```

#### 2.1.1 Data Validation Checklist

- Confirm every block has a parent except for the document root.
- Ensure dataset records include a JSON payload.
- Verify the tree is acyclic by construction.

#### 2.1.2 Error Handling

1. Reject malformed datasets early.
2. Surface descriptive validation errors to the caller.
3. Retain the raw Markdown payload to aid debugging.

### 2.2 Query Patterns

```dataset:query_patterns
{
  "records": [
    {
      "name": "Root scoped paragraphs",
      "where": {"type": "paragraph"},
      "root": {"title": "Systems Integration Handbook"}
    },
    {
      "name": "Headings under onboarding",
      "parent": {"title": "Onboarding Checklist"}
    },
    {
      "name": "Datasets tagged finance",
      "metadata": {"tags": ["finance", "risk"]}
    }
  ]
}
```

#### 2.2.1 Structural Filters

- Target block type, parent, or root identifiers.
- Combine multiple filters for precise slices.
- Limit result sets to maintain predictable UI latency.

#### 2.2.2 Semantic Filters

1. Use JSON path expressions (`properties.title`, `content.data.category`).
2. Apply boolean compositions to narrow results.
3. Support equality, containment, and membership comparisons.

### 2.3 Example Walkthrough

1. Select **Systems Integration Handbook** in the sidebar.
2. Expand the **Repository Filters** panel and set `Block type` to `paragraph`.
3. Add a parent constraint where `properties.title` contains `Checklist`.
4. Inspect the resulting blocks and confirm the hierarchy in the tree view.

## Section 3 — Onboarding Checklist

### 3.1 Pre-flight

- Confirm access to staging credentials.
- Sync feature toggles across environments.
- Review the latest architecture notes.

### 3.2 Day Zero Actions

1. Provision the integration service account.
2. Execute the base ingestion script on sample content.
3. Capture metrics for parser runtime and block counts.

### 3.3 Monitoring Grid

```dataset:monitoring_grid
{
  "records": [
    {
      "metric": "ingest_runtime_ms",
      "threshold": 250,
      "status": "pass"
    },
    {
      "metric": "blocks_created",
      "threshold": 400,
      "status": "observe"
    },
    {
      "metric": "dataset_records",
      "threshold": 120,
      "status": "pass"
    }
  ]
}
```

### 3.4 Nested Lists Demonstration

- Milestones
  - Kick-off meeting
    - Agenda drafted
    - Stakeholders invited
  - First sandbox sync
    1. Run seed scripts
    2. Validate dataset outputs
- Risks
  - Parser drift
  - Schema changes without migration

## Section 4 — Reference Notes

### 4.1 Frequently Asked Questions

1. **Can we ingest HTML?** No, transform to Markdown or use a custom renderer.
2. **How are synced blocks represented?** As references resolved in the DocumentStore layer.
3. **Is pagination supported?** Not in the POC; rely on filtered queries.

### 4.2 Future Enhancements

- Expand parser to support tables and callouts.
- Introduce HTML renderer variant.
- Add mutation APIs for secondary trees.

### 4.3 Revision History

```dataset:revision_history
{
  "records": [
    {
      "version": "v0.1",
      "summary": "Initial synthetic long-form document."
    },
    {
      "version": "v0.2",
      "summary": "Added monitoring dataset and nested list examples."
    }
  ]
}
```

### 4.4 Closing Thoughts

This synthetic handbook demonstrates a moderately deep block tree, multiple datasets, and combined list structures. Use it to validate query performance, renderer output, and UI responsiveness within the POC scope.



# Iteration 4

# Systems Integration Handbook

Welcome to the systems integration handbook for the Decipher POC environment. This document is intentionally long to demonstrate tree depth, nested structures, and dataset handling.

## Objectives

1. Establish a consistent vocabulary for integration partners.
2. Showcase how multi-level headings, lists, and datasets are represented in the block data store.
3. Provide a reusable template that can be extended for production scenarios.

## Section 1 — Canonical Model Overview

### 1.1 Terminology

- **Canonical tree**: The primary hierarchy rooted at the document block.
- **Secondary tree**: Alternative perspectives composed with synced references.
- **Block**: Typed entity with properties, metadata, and optional content payloads.

### 1.2 Key Responsibilities

1. Persist every block with deterministic identifiers.
2. Maintain referential integrity across parent-child relationships.
3. Enable filtered projections over structure, metadata, and JSON content.

### 1.3 Supported Block Types

- Document
  - Heading
    - Paragraph
    - Bulleted list item
    - Numbered list item
- Dataset
  - Record

### 1.4 Operational Constraints

> Note: The POC parser intentionally limits supported Markdown features to a minimal but expressive subset.

## Section 2 — Integration Playbook

### 2.1 Ingestion Pipeline

```dataset:ingestion_flow
{
  "records": [
    {
      "step": "Parse markdown",
      "description": "Convert author-facing content into typed blocks."
    },
    {
      "step": "Normalize identifiers",
      "description": "Assign deterministic UUIDs for reproducible references."
    },
    {
      "step": "Persist",
      "description": "Store blocks via the repository layer using SQLAlchemy."
    }
  ]
}
```

#### 2.1.1 Data Validation Checklist

- Confirm every block has a parent except for the document root.
- Ensure dataset records include a JSON payload.
- Verify the tree is acyclic by construction.

#### 2.1.2 Error Handling

1. Reject malformed datasets early.
2. Surface descriptive validation errors to the caller.
3. Retain the raw Markdown payload to aid debugging.

### 2.2 Query Patterns

```dataset:query_patterns
{
  "records": [
    {
      "name": "Root scoped paragraphs",
      "where": {"type": "paragraph"},
      "root": {"title": "Systems Integration Handbook"}
    },
    {
      "name": "Headings under onboarding",
      "parent": {"title": "Onboarding Checklist"}
    },
    {
      "name": "Datasets tagged finance",
      "metadata": {"tags": ["finance", "risk"]}
    }
  ]
}
```

#### 2.2.1 Structural Filters

- Target block type, parent, or root identifiers.
- Combine multiple filters for precise slices.
- Limit result sets to maintain predictable UI latency.

#### 2.2.2 Semantic Filters

1. Use JSON path expressions (`properties.title`, `content.data.category`).
2. Apply boolean compositions to narrow results.
3. Support equality, containment, and membership comparisons.

### 2.3 Example Walkthrough

1. Select **Systems Integration Handbook** in the sidebar.
2. Expand the **Repository Filters** panel and set `Block type` to `paragraph`.
3. Add a parent constraint where `properties.title` contains `Checklist`.
4. Inspect the resulting blocks and confirm the hierarchy in the tree view.

## Section 3 — Onboarding Checklist

### 3.1 Pre-flight

- Confirm access to staging credentials.
- Sync feature toggles across environments.
- Review the latest architecture notes.

### 3.2 Day Zero Actions

1. Provision the integration service account.
2. Execute the base ingestion script on sample content.
3. Capture metrics for parser runtime and block counts.

### 3.3 Monitoring Grid

```dataset:monitoring_grid
{
  "records": [
    {
      "metric": "ingest_runtime_ms",
      "threshold": 250,
      "status": "pass"
    },
    {
      "metric": "blocks_created",
      "threshold": 400,
      "status": "observe"
    },
    {
      "metric": "dataset_records",
      "threshold": 120,
      "status": "pass"
    }
  ]
}
```

### 3.4 Nested Lists Demonstration

- Milestones
  - Kick-off meeting
    - Agenda drafted
    - Stakeholders invited
  - First sandbox sync
    1. Run seed scripts
    2. Validate dataset outputs
- Risks
  - Parser drift
  - Schema changes without migration

## Section 4 — Reference Notes

### 4.1 Frequently Asked Questions

1. **Can we ingest HTML?** No, transform to Markdown or use a custom renderer.
2. **How are synced blocks represented?** As references resolved in the DocumentStore layer.
3. **Is pagination supported?** Not in the POC; rely on filtered queries.

### 4.2 Future Enhancements

- Expand parser to support tables and callouts.
- Introduce HTML renderer variant.
- Add mutation APIs for secondary trees.

### 4.3 Revision History

```dataset:revision_history
{
  "records": [
    {
      "version": "v0.1",
      "summary": "Initial synthetic long-form document."
    },
    {
      "version": "v0.2",
      "summary": "Added monitoring dataset and nested list examples."
    }
  ]
}
```

### 4.4 Closing Thoughts

This synthetic handbook demonstrates a moderately deep block tree, multiple datasets, and combined list structures. Use it to validate query performance, renderer output, and UI responsiveness within the POC scope.



# Iteration 5

# Systems Integration Handbook

Welcome to the systems integration handbook for the Decipher POC environment. This document is intentionally long to demonstrate tree depth, nested structures, and dataset handling.

## Objectives

1. Establish a consistent vocabulary for integration partners.
2. Showcase how multi-level headings, lists, and datasets are represented in the block data store.
3. Provide a reusable template that can be extended for production scenarios.

## Section 1 — Canonical Model Overview

### 1.1 Terminology

- **Canonical tree**: The primary hierarchy rooted at the document block.
- **Secondary tree**: Alternative perspectives composed with synced references.
- **Block**: Typed entity with properties, metadata, and optional content payloads.

### 1.2 Key Responsibilities

1. Persist every block with deterministic identifiers.
2. Maintain referential integrity across parent-child relationships.
3. Enable filtered projections over structure, metadata, and JSON content.

### 1.3 Supported Block Types

- Document
  - Heading
    - Paragraph
    - Bulleted list item
    - Numbered list item
- Dataset
  - Record

### 1.4 Operational Constraints

> Note: The POC parser intentionally limits supported Markdown features to a minimal but expressive subset.

## Section 2 — Integration Playbook

### 2.1 Ingestion Pipeline

```dataset:ingestion_flow
{
  "records": [
    {
      "step": "Parse markdown",
      "description": "Convert author-facing content into typed blocks."
    },
    {
      "step": "Normalize identifiers",
      "description": "Assign deterministic UUIDs for reproducible references."
    },
    {
      "step": "Persist",
      "description": "Store blocks via the repository layer using SQLAlchemy."
    }
  ]
}
```

#### 2.1.1 Data Validation Checklist

- Confirm every block has a parent except for the document root.
- Ensure dataset records include a JSON payload.
- Verify the tree is acyclic by construction.

#### 2.1.2 Error Handling

1. Reject malformed datasets early.
2. Surface descriptive validation errors to the caller.
3. Retain the raw Markdown payload to aid debugging.

### 2.2 Query Patterns

```dataset:query_patterns
{
  "records": [
    {
      "name": "Root scoped paragraphs",
      "where": {"type": "paragraph"},
      "root": {"title": "Systems Integration Handbook"}
    },
    {
      "name": "Headings under onboarding",
      "parent": {"title": "Onboarding Checklist"}
    },
    {
      "name": "Datasets tagged finance",
      "metadata": {"tags": ["finance", "risk"]}
    }
  ]
}
```

#### 2.2.1 Structural Filters

- Target block type, parent, or root identifiers.
- Combine multiple filters for precise slices.
- Limit result sets to maintain predictable UI latency.

#### 2.2.2 Semantic Filters

1. Use JSON path expressions (`properties.title`, `content.data.category`).
2. Apply boolean compositions to narrow results.
3. Support equality, containment, and membership comparisons.

### 2.3 Example Walkthrough

1. Select **Systems Integration Handbook** in the sidebar.
2. Expand the **Repository Filters** panel and set `Block type` to `paragraph`.
3. Add a parent constraint where `properties.title` contains `Checklist`.
4. Inspect the resulting blocks and confirm the hierarchy in the tree view.

## Section 3 — Onboarding Checklist

### 3.1 Pre-flight

- Confirm access to staging credentials.
- Sync feature toggles across environments.
- Review the latest architecture notes.

### 3.2 Day Zero Actions

1. Provision the integration service account.
2. Execute the base ingestion script on sample content.
3. Capture metrics for parser runtime and block counts.

### 3.3 Monitoring Grid

```dataset:monitoring_grid
{
  "records": [
    {
      "metric": "ingest_runtime_ms",
      "threshold": 250,
      "status": "pass"
    },
    {
      "metric": "blocks_created",
      "threshold": 400,
      "status": "observe"
    },
    {
      "metric": "dataset_records",
      "threshold": 120,
      "status": "pass"
    }
  ]
}
```

### 3.4 Nested Lists Demonstration

- Milestones
  - Kick-off meeting
    - Agenda drafted
    - Stakeholders invited
  - First sandbox sync
    1. Run seed scripts
    2. Validate dataset outputs
- Risks
  - Parser drift
  - Schema changes without migration

## Section 4 — Reference Notes

### 4.1 Frequently Asked Questions

1. **Can we ingest HTML?** No, transform to Markdown or use a custom renderer.
2. **How are synced blocks represented?** As references resolved in the DocumentStore layer.
3. **Is pagination supported?** Not in the POC; rely on filtered queries.

### 4.2 Future Enhancements

- Expand parser to support tables and callouts.
- Introduce HTML renderer variant.
- Add mutation APIs for secondary trees.

### 4.3 Revision History

```dataset:revision_history
{
  "records": [
    {
      "version": "v0.1",
      "summary": "Initial synthetic long-form document."
    },
    {
      "version": "v0.2",
      "summary": "Added monitoring dataset and nested list examples."
    }
  ]
}
```

### 4.4 Closing Thoughts

This synthetic handbook demonstrates a moderately deep block tree, multiple datasets, and combined list structures. Use it to validate query performance, renderer output, and UI responsiveness within the POC scope.

