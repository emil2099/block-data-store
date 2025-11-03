# **Architectural Overview: A Simple Grouping Model**

Version: 1.2  
Status: Adopted

## **1\. The Problem: Semantic Structure vs. Page Groups**

We have two ways of looking at a document:

1. **The Canonical Tree:** This is the *semantic* structure you author (document \-\> section \-\> list \-\> list item). It is the single source of truth for content, and its order is defined by children\_ids.  
2. **A Grouping:** This is a "view" that cuts *across* the canonical tree, like:  
   * Physical Pages (from a PDF)  
   * AI Chunks (for RAG)

The core challenge is that these two structures don't align. The clearest example is your "split bullet list":

* A list\_block contains 4 list\_item children.  
* In the canonical tree, they are all siblings, one after the other.  
* But in the "Page" grouping, a page break splits them:  
  * list\_item\_1 \-\> on Page 1  
  * list\_item\_2 \-\> on Page 1  
  * list\_item\_3 \-\> on Page 2  
  * list\_item\_4 \-\> on Page 2

We need a simple model that lets us render "Page 2" and see list\_item\_3 and list\_item\_4 (in that order), without breaking the canonical tree.

## **2\. The Solution: "Inverted Tags"**

The simplest solution is to **invert the relationship**. Instead of groups *owning* blocks, blocks *tag themselves* with the groups they belong to.  
This avoids creating complex "secondary trees" or synced blocks and aligns with our "Typed properties, free-form metadata" principle.

## **3\. How It Works: A 3-Step Model**

### **Step 1: Groups are "Anchor" Blocks**

* A group (like "Page 1") is its own block, e.g., type: "page\_group".  
* This block holds metadata *about* the group (e.g., properties: {page\_number: 1, classification: "Pricing"}).  
* To set the order of pages (1, 2, 3...), we make them children of a single page\_index block.

**Example Structure:**  
\[document\] (id: "doc-root")  
  │  
  ├─ \[list\_block\] (id: "list-1")  
  │    ├─ \[list\_item\] (id: "item-1")  
  │    ├─ \[list\_item\] (id: "item-2")  
  │    ├─ \[list\_item\] (id: "item-3")  
  │    └─ \[list\_item\] (id: "item-4")  
  │  
  └─ \[page\_group\_index\] (id: "page-index")  
       │  
       ├─ \[page\_group\] (id: "page-1-uuid", props: {num: 1})  
       └─ \[page\_group\] (id: "page-2-uuid", props: {num: 2})

### **Step 2: Content Blocks "Tag" Themselves**

This is the core of the solution. We use the **properties** field on the canonical blocks to store a list of group(s) they belong to. This is defined in each block's typed Properties model (e.g., ParagraphProps, ListItemProps).

* list\_item\_2 (on Page 1):  
  {  
    "id": "item-2",  
    "parent\_id": "list-1",  
    "type": "list\_item",  
    "properties": { "groups": \["page-1-uuid"\] }  
  }

* list\_item\_3 (on Page 2):  
  {  
    "id": "item-3",  
    "parent\_id": "list-1",  
    "type": "list\_item",  
    "properties": { "groups": \["page-2-uuid"\] }  
  }

This model also solves the "split paragraph" problem: a single paragraph block that starts on Page 1 and ends on Page 2 would simply tag itself with both page IDs:  
"properties": { "groups": \["page-1-uuid", "page-2-uuid"\] }

### **Step 3: How to Render "Page 2"**

To render a group, the logic is simple and robust:

1. **Fetch:** Get all blocks where properties.groups contains "page-2-uuid".  
   * *This will return \[item-3, item-4, ...\] in any order.*  
2. **Sort:** Sort these fetched blocks using their **canonical tree order** (i.e., by their parent\_id and position in children\_ids).  
   * *This guarantees item-3 comes before item-4.*  
3. **Render:** Display the sorted list of blocks.

## **4\. Why This Model is Better**

* **Simple:** It uses the existing properties schema. It does **not** require complex synced blocks.  
* **Correct Order:** It guarantees render order is *always* consistent with the canonical source of truth.  
* **Flexible:** It cleanly solves both the "split list" and "split paragraph" problems.  
* **Efficient:** It's easy to find a block's groups (read its properties) and a group's blocks (query the properties.groups array).

## **5\. Risks and Mitigations**

This model is robust, but it introduces two specific challenges that must be handled at the application layer.

### **5.1. Risk: Sort & Render Complexity**

* **Risk:** The "Step 2: Sort" logic, which derives order from the canonical tree, can be complex and slow if not implemented carefully. Operations that walk the tree (like sorting or calculating indents) cannot be done lazily with individual database calls (N+1 query problem).  
* **Mitigation:** The DocumentStore and Renderer layers must be designed around this. The Renderer must be given a fully-hydrated, in-memory tree to walk. This pushes the performance cost to the initial load, rather than the render-time logic.

### **5.2. Risk: Dangling References**

* **Risk:** The properties.groups array stores "dumb" UUIDs. If a page\_group block (e.g., "page-1-uuid") is deleted, any content blocks still referencing it will have a "dangling" UUID, which can cause data pollution and render errors.  
* **Mitigation:** This must be handled by the DocumentStore (application) layer. When a group block is deleted, the DocumentStore is responsible for running a cleanup query to find all blocks that reference that group\_id and remove it from their properties.groups array.