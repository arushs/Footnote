# RAG Evaluation Harness

Evaluate RAG quality by running queries against local documents.

## Usage

```bash
cd backend

# Simple RAG (vector search + answer)
uv run python eval/run_eval.py --folder ./eval/dataset

# Full Agent RAG (real agent loop with tools, requires database)
uv run python eval/run_eval.py --folder ./eval/dataset --agent
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `--folder` | Path to folder with documents (required) | - |
| `-d, --dataset` | Path to eval dataset JSON | `eval/dataset.json` |
| `-o, --out` | Output HTML report path | `eval/report.html` |
| `-k, --k-doc` | Top-K for retrieval | `10` |
| `--agent` | Use full agentic RAG with database | `false` |

## Supported File Types

- **Text**: `.txt`, `.md`, `.json`, `.py`, `.html`, `.csv`, `.xml`, `.yaml`, `.yml`, `.rst`, `.log`
- **PDF**: Extracted via Mistral OCR

## Dataset Format

```json
{
  "meta": {
    "name": "my_eval_set",
    "k_doc": 10
  },
  "items": [
    {
      "id": "E001",
      "query": "What was Q1 revenue?",
      "gold_doc_titles": ["10-Q Q1"],
      "requires_tool": true,
      "expected_tool": "search_folder",
      "tags": ["financial"]
    }
  ]
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier |
| `query` | Yes | Question to ask |
| `gold_doc_titles` | Yes | Doc names that should be retrieved/cited (substring match) |
| `requires_tool` | No | Whether a tool call is expected (default: true) |
| `expected_tool` | No | Specific tool name to check for |
| `tags` | No | Labels for filtering/grouping |

## Metrics

| Metric | Pass Condition |
|--------|----------------|
| **Doc Recall** | Any gold doc in top-K retrieved |
| **Citation Hit** | Any gold doc cited in answer |
| **Tool Correct** | Expected tool was called (agent mode) |

**Pass**: All metrics = 1

## Modes

### Simple RAG (default)

1. Embed query
2. Vector search for top-K chunks
3. Send to Claude with context
4. Score response

No database required. Uses existing `embed_query()` and `embed_documents_batch()`.

### Agent RAG (`--agent`)

1. Create temp folder in database with documents
2. Run real `agentic_rag()` with tool use loop
3. Score response
4. Clean up temp data

Requires database connection. Tests the full agent pipeline including `search_folder`, `get_file_chunks`, and `get_file` tools.

## Output

Generates `eval/report.html` with:

- Pass rate and metric averages
- Per-item results (expandable)
- Retrieved docs, citations, tool calls, answer preview

## Requirements

```bash
# Environment variables in .env
FIREWORKS_API_KEY=...   # For embeddings
ANTHROPIC_API_KEY=...   # For Claude
MISTRAL_API_KEY=...     # For PDF OCR

# For --agent mode
DATABASE_URL=...        # Postgres with pgvector
```
