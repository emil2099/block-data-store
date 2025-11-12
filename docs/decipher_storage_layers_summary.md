# Decipher Storage Architecture – Layered Design Summary

## 1. Core Principles
- The **Domain Service** is the *single entry point* for all operations related to blocks and block graphs (including reads and writes).
- The **Repository** is an internal, persistence-focused component responsible only for interacting with the database efficiently.
- The Domain Service returns fully hydrated structures ready for use by application code, insulating callers from storage concerns.

---

## 2. Layer Responsibilities

### **Domain Service (Public API)**
**Purpose:** Represents Decipher’s business logic surface. It defines and enforces the rules of the block graph model and coordinates persistence and side effects.

**Responsibilities:**
- Provide intuitive application-facing methods (e.g. get subtree, insert block, move block).
- Enforce invariants (single canonical parent, parent-owned ordering, valid group associations, version control).
- Orchestrate multi-step operations that span multiple blocks.
- Trigger side effects (e.g. vector index updates, cache invalidation, audit events).
- Return hydrated models or trees directly to callers.

**Key property:** *Callers never interact directly with the repository.*

---

### **Repository (Internal Adapter)**
**Purpose:** Provides efficient, low-level access to storage. It abstracts database access details and exposes a minimal set of persistence operations.

**Responsibilities:**
- Execute queries and return raw or lightly shaped block data.
- Persist individual blocks or batch updates (e.g. set children, update node contents, delete block).
- Perform data hydration where it can be done efficiently (e.g. hierarchical queries).
- No orchestration, no business rules, no side effects.

**Key property:** *Implements "how data is stored and retrieved", not "what the system is allowed to do".*

---

## 3. Interaction Flow
1. Application or agents call **Domain Service**.
2. Domain Service applies rules, composes operations, and calls Repository.
3. Repository performs persistence tasks efficiently.
4. Domain Service hydrates and returns complete models ready for use.

---

## 4. Benefits of This Design
- **Simplicity:** One clear API surface for application code.
- **Consistency:** All rules and side effects are enforced in one place.
- **Extensibility:** Future features (vector indexing, version history, derived views) plug into the Domain Service without changing callers.
- **Performance Control:** Repository remains optimised for storage, without mixing in business complexity.

---

## 5. Guiding Rule for Engineers
> **"If you need to work with blocks or block graphs, call the Domain Service. The Repository is internal and should not be called directly."**
