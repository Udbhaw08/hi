# Complete Code Knowledge Graph Build

The goal is to provide a complete, interactive knowledge graph for the `Drishti-full` project. Currently, the graph exists but is missing critical metadata like execution flows and code communities, which prevents advanced analysis and architectural overviews.

## Proposed Changes

We will use the `code-review-graph` toolset to fully analyze the codebase.

### Graph Infrastructure

#### [REBUILD] Code Knowledge Graph
We will perform a full rebuild of the graph database. This will:
- Re-parse all Python and JavaScript files.
- Re-calculate function call chains (Flows).
- Re-cluster related code entities into Communities (Leiden algorithm).
- Update cross-community dependency metrics.

#### [NEW] Semantic Embeddings
We will compute vector embeddings for all code nodes.
- This enables **semantic search**, allowing you to find code by intent (e.g., "how is face detection gated?") rather than just keyword matching.
- Default model: `all-MiniLM-L6-v2`.

#### [NEW] Developer Wiki
We will generate a markdown-based wiki in `.code-review-graph/wiki/`.
- This provides an offline, readable documentation of all detected communities and their internal structures.

## Open Questions

- **Execution Time**: A full rebuild and embedding phase can take 1-3 minutes depending on CPU/GPU availability for the embedding model. Should I proceed with both? (Recommended for full functionality).

## Verification Plan

### Automated Verification
- Run `list_graph_stats` to verify node/edge/embedding counts.
- Run `get_architecture_overview` to ensure communities are correctly mapped.
- Run `list_flows` to verify entry-point detection.

### Manual Verification
- Provide a summary of the top 3 largest communities detected.
- Showcase a semantic search example.
