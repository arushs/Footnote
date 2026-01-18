#!/usr/bin/env python3
"""RAG Evaluation Harness.

Tests RAG quality by loading documents from a local folder.
Supports both simple RAG and full agentic RAG.

Usage:
    cd backend

    # Simple RAG (retrieve once, answer)
    uv run python eval/run_eval.py --folder ./path/to/docs

    # Full agentic RAG (real agent loop with tool use)
    uv run python eval/run_eval.py --folder ./path/to/docs --agent
"""

import argparse
import asyncio
import json
import re
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.services.anthropic import get_client
from app.services.file.chunking import chunk_document
from app.services.file.embedding import embed_documents_batch, embed_query
from app.services.file.extraction import TextBlock
from app.services.file.extraction.pdf import PDFExtractor

# =============================================================================
# DATA MODELS
# =============================================================================


class EvalItem(BaseModel):
    id: str
    query: str
    gold_doc_titles: list[str]
    requires_tool: bool = True
    expected_tool: str | None = None
    tags: list[str] = []


class EvalDataset(BaseModel):
    meta: dict
    items: list[EvalItem]


@dataclass
class Document:
    name: str
    path: Path
    blocks: list[TextBlock]


@dataclass
class EvalChunk:
    """Chunk with embedding for eval."""

    doc_name: str
    text: str
    location: dict
    embedding: list[float] | None = None


@dataclass
class SystemResponse:
    answer: str
    citations: list[str]  # doc names cited
    tool_calls: list[str]
    retrieved: list[str]  # doc names retrieved
    latency_ms: float


@dataclass
class ItemResult:
    item: EvalItem
    response: SystemResponse
    doc_recall: int  # 0 or 1
    citation_hit: int  # 0 or 1
    tool_correct: int  # 0 or 1
    passed: bool
    failure_reasons: list[str] = field(default_factory=list)


# =============================================================================
# DOCUMENT LOADING (using existing extraction services)
# =============================================================================


TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".py",
    ".html",
    ".csv",
    ".xml",
    ".yaml",
    ".yml",
    ".rst",
    ".log",
}


def text_to_blocks(content: str, file_name: str) -> list[TextBlock]:
    """Convert plain text to TextBlocks."""
    blocks = []
    paragraphs = content.split("\n\n")

    for i, para in enumerate(paragraphs):
        text = para.strip()
        if text:
            blocks.append(
                TextBlock(
                    text=text,
                    location={"type": "text", "paragraph": i, "file": file_name},
                )
            )

    return blocks


async def load_documents(folder: Path) -> list[Document]:
    """Load documents from a folder using existing extraction services."""
    docs = []
    pdf_extractor = PDFExtractor()

    all_files = list(folder.rglob("*"))
    text_files = [f for f in all_files if f.is_file() and f.suffix.lower() in TEXT_EXTENSIONS]
    pdf_files = [f for f in all_files if f.is_file() and f.suffix.lower() == ".pdf"]

    # Load text files
    for path in text_files:
        try:
            content = path.read_text(encoding="utf-8")
            blocks = text_to_blocks(content, path.name)
            if blocks:
                docs.append(Document(name=path.name, path=path, blocks=blocks))
        except Exception as e:
            print(f"  Warning: Could not read {path.name}: {e}")

    # Load PDFs with Mistral OCR
    if pdf_files:
        print(f"  Extracting {len(pdf_files)} PDFs with Mistral OCR...")
        for path in pdf_files:
            try:
                pdf_content = path.read_bytes()
                extracted = await pdf_extractor.extract(pdf_content)
                if extracted.blocks:
                    docs.append(Document(name=path.name, path=path, blocks=extracted.blocks))
                    print(f"    ✓ {path.name} ({len(extracted.blocks)} blocks)")
                else:
                    print(f"    ✗ {path.name} (no text extracted)")
            except Exception as e:
                print(f"    ✗ {path.name}: {e}")

    return docs


def create_chunks(docs: list[Document]) -> list[EvalChunk]:
    """Create chunks from documents using existing chunking service."""
    eval_chunks = []

    for doc in docs:
        doc_chunks = chunk_document(doc.blocks)
        for chunk in doc_chunks:
            eval_chunks.append(
                EvalChunk(
                    doc_name=doc.name,
                    text=chunk.text,
                    location=chunk.location,
                )
            )

    return eval_chunks


async def embed_chunks(chunks: list[EvalChunk]) -> None:
    """Embed chunks using existing embedding service."""
    texts = [c.text for c in chunks]
    embeddings = await embed_documents_batch(texts)
    for chunk, emb in zip(chunks, embeddings, strict=True):
        chunk.embedding = emb


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0


async def retrieve_chunks(query: str, chunks: list[EvalChunk], k: int = 10) -> list[EvalChunk]:
    """Retrieve top-k chunks by similarity using existing embedding service."""
    query_embedding = await embed_query(query)

    scored = []
    for chunk in chunks:
        if chunk.embedding:
            score = cosine_similarity(query_embedding, chunk.embedding)
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored[:k]]


# =============================================================================
# SIMPLE RAG
# =============================================================================


SIMPLE_RAG_PROMPT = """You are a helpful assistant that answers questions based on the provided documents.

## Response Format
- Keep responses short and scannable
- Use markdown for structure when helpful

## Citations
- Use [N] notation to cite sources
- Reference the document name in citations

## Context
The following documents have been retrieved for your reference:

{context}

Answer the user's question based ONLY on the provided context. If you can't find the answer, say so."""


async def run_simple_rag(
    query: str,
    chunks: list[EvalChunk],
    k: int = 10,
) -> SystemResponse:
    """Run simple RAG: retrieve once, answer."""
    start = perf_counter()

    # Retrieve relevant chunks
    retrieved_chunks = await retrieve_chunks(query, chunks, k=k)
    retrieved_docs = list(dict.fromkeys(c.doc_name for c in retrieved_chunks))

    # Build context
    context_parts = []
    for i, chunk in enumerate(retrieved_chunks, 1):
        context_parts.append(f"[{i}] From {chunk.doc_name}:\n{chunk.text[:1000]}")
    context = "\n\n".join(context_parts)

    # Call Claude
    client = get_client()
    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=2048,
        system=SIMPLE_RAG_PROMPT.format(context=context),
        messages=[{"role": "user", "content": query}],
    )

    answer = ""
    if response.content and hasattr(response.content[0], "text"):
        answer = response.content[0].text

    # Extract citations
    citation_nums = set(int(m) for m in re.findall(r"\[(\d+)\]", answer))
    cited_docs = []
    for num in citation_nums:
        if 1 <= num <= len(retrieved_chunks):
            cited_docs.append(retrieved_chunks[num - 1].doc_name)
    cited_docs = list(dict.fromkeys(cited_docs))

    latency_ms = (perf_counter() - start) * 1000

    return SystemResponse(
        answer=answer,
        citations=cited_docs,
        tool_calls=[],
        retrieved=retrieved_docs,
        latency_ms=latency_ms,
    )


# =============================================================================
# FULL AGENTIC RAG (using real agent loop)
# =============================================================================


async def run_agent_rag(
    query: str,
    folder_id: uuid.UUID,
    user_id: uuid.UUID,
) -> SystemResponse:
    """Run the full agentic RAG loop using the real agent code."""
    from sqlalchemy import select

    from app.database import get_task_session
    from app.models import Conversation, File, Folder
    from app.services.chat.agent import agentic_rag

    start = perf_counter()
    answer = ""
    tool_calls = []
    citations = {}
    searched_files = []

    async with get_task_session() as db:
        folder = await db.get(Folder, folder_id)
        if not folder:
            raise ValueError(f"Folder {folder_id} not found")

        files_result = await db.execute(select(File).where(File.folder_id == folder_id))
        files = files_result.scalars().all()

        conversation = Conversation(folder_id=folder_id)
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

        try:
            async for chunk in agentic_rag(
                db=db,
                folder_id=folder_id,
                user_id=user_id,
                conversation=conversation,
                user_message=query,
                folder_name=folder.folder_name or "Eval Folder",
                files_indexed=len([f for f in files if f.index_status == "indexed"]),
                files_total=len(files),
                max_iterations=10,
            ):
                if not chunk.startswith("data: "):
                    continue
                data = chunk[6:].strip()
                if not data:
                    continue

                try:
                    parsed = json.loads(data)
                    if "token" in parsed:
                        answer += parsed["token"]
                    elif "agent_status" in parsed and "tool" in parsed["agent_status"]:
                        tool_calls.append(parsed["agent_status"]["tool"])
                    elif parsed.get("done"):
                        citations = parsed.get("citations", {})
                        searched_files = parsed.get("searched_files", [])
                except json.JSONDecodeError:
                    pass

        finally:
            await db.delete(conversation)
            await db.commit()

    cited_docs = []
    if isinstance(citations, dict):
        for c in citations.values():
            if isinstance(c, dict) and "file_name" in c:
                cited_docs.append(c["file_name"])
    cited_docs = list(dict.fromkeys(cited_docs))

    latency_ms = (perf_counter() - start) * 1000

    return SystemResponse(
        answer=answer,
        citations=cited_docs,
        tool_calls=tool_calls,
        retrieved=searched_files,
        latency_ms=latency_ms,
    )


async def setup_temp_folder(
    docs: list[Document], chunks: list[EvalChunk]
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a temporary folder with indexed documents in the database."""
    from sqlalchemy import text

    from app.database import get_task_session
    from app.models import Chunk as ChunkModel
    from app.models import File, Folder, User

    async with get_task_session() as db:
        result = await db.execute(
            text("SELECT id FROM users WHERE email = 'eval@test.local' LIMIT 1")
        )
        row = result.fetchone()

        if row:
            user_id = row[0]
        else:
            user = User(google_id="eval-user", email="eval@test.local")
            db.add(user)
            await db.commit()
            await db.refresh(user)
            user_id = user.id

        folder = Folder(
            user_id=user_id,
            google_folder_id=f"eval-{uuid.uuid4().hex[:8]}",
            folder_name="Eval Test Folder",
            index_status="ready",
        )
        db.add(folder)
        await db.commit()
        await db.refresh(folder)

        doc_to_file: dict[str, uuid.UUID] = {}
        for doc in docs:
            preview = "\n".join(b.text[:100] for b in doc.blocks[:3])
            file = File(
                folder_id=folder.id,
                google_file_id=f"eval-file-{uuid.uuid4().hex[:8]}",
                file_name=doc.name,
                mime_type="text/plain",
                index_status="indexed",
                file_preview=preview[:500],
            )
            db.add(file)
            await db.commit()
            await db.refresh(file)
            doc_to_file[doc.name] = file.id

        chunk_index = 0
        for chunk in chunks:
            file_id = doc_to_file.get(chunk.doc_name)
            if not file_id or not chunk.embedding:
                continue

            chunk_model = ChunkModel(
                file_id=file_id,
                user_id=user_id,
                chunk_text=chunk.text,
                chunk_embedding=chunk.embedding,
                location=chunk.location,
                chunk_index=chunk_index,
            )
            db.add(chunk_model)
            chunk_index += 1

        await db.commit()
        return folder.id, user_id


async def cleanup_temp_folder(folder_id: uuid.UUID):
    """Remove temporary folder and all its data."""
    from sqlalchemy import text

    from app.database import get_task_session

    async with get_task_session() as db:
        await db.execute(
            text("""
            DELETE FROM chunks WHERE file_id IN (
                SELECT id FROM files WHERE folder_id = :folder_id
            )
        """),
            {"folder_id": folder_id},
        )

        await db.execute(
            text("""
            DELETE FROM messages WHERE conversation_id IN (
                SELECT id FROM conversations WHERE folder_id = :folder_id
            )
        """),
            {"folder_id": folder_id},
        )

        await db.execute(
            text("DELETE FROM conversations WHERE folder_id = :folder_id"), {"folder_id": folder_id}
        )
        await db.execute(
            text("DELETE FROM files WHERE folder_id = :folder_id"), {"folder_id": folder_id}
        )
        await db.execute(
            text("DELETE FROM folders WHERE id = :folder_id"), {"folder_id": folder_id}
        )
        await db.commit()


# =============================================================================
# SCORING
# =============================================================================


def title_matches(a: str, b: str) -> bool:
    """Case-insensitive bidirectional substring match."""
    a_lower = a.lower()
    b_lower = b.lower()
    return a_lower in b_lower or b_lower in a_lower


def score_item(item: EvalItem, response: SystemResponse, k: int) -> ItemResult:
    """Score a single eval item."""
    failure_reasons = []

    doc_recall = 0
    if not item.gold_doc_titles:
        doc_recall = 1
    else:
        for gold in item.gold_doc_titles:
            if any(title_matches(hit, gold) for hit in response.retrieved[:k]):
                doc_recall = 1
                break
    if doc_recall == 0:
        failure_reasons.append(f"Doc recall: gold docs not in top-{k} retrieved")

    citation_hit = 0
    if not item.gold_doc_titles:
        citation_hit = 1 if not response.citations else 0
    else:
        for gold in item.gold_doc_titles:
            if any(title_matches(cite, gold) for cite in response.citations):
                citation_hit = 1
                break
    if citation_hit == 0:
        failure_reasons.append("Citation hit: no citation matches gold doc")

    tool_correct = 1
    if item.requires_tool and item.expected_tool:
        tool_names = [t.lower() for t in response.tool_calls]
        if item.expected_tool.lower() not in tool_names:
            tool_correct = 0
            failure_reasons.append(f'Tool correct: expected "{item.expected_tool}"')

    passed = doc_recall == 1 and citation_hit == 1 and tool_correct == 1

    return ItemResult(
        item=item,
        response=response,
        doc_recall=doc_recall,
        citation_hit=citation_hit,
        tool_correct=tool_correct,
        passed=passed,
        failure_reasons=failure_reasons,
    )


# =============================================================================
# HTML REPORT
# =============================================================================


def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def generate_html_report(
    dataset: EvalDataset, results: list[ItemResult], folder: str, agent_mode: bool
) -> str:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    pass_rate = passed / total if total > 0 else 0
    avg_latency = sum(r.response.latency_ms for r in results) / total if total > 0 else 0

    avg_doc_recall = sum(r.doc_recall for r in results) / total if total > 0 else 0
    avg_citation_hit = sum(r.citation_hit for r in results) / total if total > 0 else 0
    avg_tool_correct = sum(r.tool_correct for r in results) / total if total > 0 else 0

    def stat_color(val: float) -> str:
        if val >= 0.9:
            return "good"
        if val >= 0.7:
            return "warn"
        return "bad"

    results_html = ""
    for r in results:
        failures_html = ""
        if r.failure_reasons:
            failures_html = f"""
        <div class="failures">
          <ul class="list">{"".join(f"<li>{escape_html(f)}</li>" for f in r.failure_reasons)}</ul>
        </div>"""

        tools_html = ""
        if r.response.tool_calls:
            tools_html = f"""
        <div class="section">
          <div class="section-title">Tools ({len(r.response.tool_calls)})</div>
          <ul class="list">{"".join(f"<li>{escape_html(t)}</li>" for t in r.response.tool_calls)}</ul>
        </div>"""

        results_html += f"""
    <div class="result">
      <div class="result-header" onclick="this.parentElement.classList.toggle('open')">
        <span class="badge {"pass" if r.passed else "fail"}">{"PASS" if r.passed else "FAIL"}</span>
        <span class="query">{escape_html(r.item.query)}</span>
        <span class="latency">{r.response.latency_ms:.0f}ms</span>
      </div>
      <div class="details">
        <div class="metrics">
          <span class="metric {"fail" if r.doc_recall == 0 else ""}">DocRecall: {r.doc_recall}</span>
          <span class="metric {"fail" if r.citation_hit == 0 else ""}">CitationHit: {r.citation_hit}</span>
          <span class="metric {"fail" if r.tool_correct == 0 else ""}">ToolCorrect: {r.tool_correct}</span>
        </div>{failures_html}
        <div class="section">
          <div class="section-title">Retrieved ({len(r.response.retrieved)})</div>
          <ul class="list">{"".join(f"<li>{escape_html(f)}</li>" for f in r.response.retrieved[:5])}</ul>
        </div>
        <div class="section">
          <div class="section-title">Citations ({len(r.response.citations)})</div>
          <ul class="list">{"".join(f"<li>{escape_html(c)}</li>" for c in r.response.citations)}</ul>
        </div>{tools_html}
        <div class="section">
          <div class="section-title">Answer</div>
          <div class="answer">{escape_html(r.response.answer[:500])}{"..." if len(r.response.answer) > 500 else ""}</div>
        </div>
      </div>
    </div>"""

    mode_label = "Agent" if agent_mode else "Simple"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>RAG Eval: {escape_html(folder)}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ font-family: system-ui, sans-serif; max-width: 1000px; margin: 0 auto; padding: 2rem; background: #f5f5f5; }}
    h1 {{ margin-bottom: 0.5rem; }}
    .meta {{ color: #666; margin-bottom: 1.5rem; }}
    .summary {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 2rem; }}
    .stat {{ background: white; padding: 1rem 1.5rem; border-radius: 8px; text-align: center; }}
    .stat-value {{ font-size: 1.75rem; font-weight: bold; }}
    .stat-value.good {{ color: #22c55e; }}
    .stat-value.warn {{ color: #f59e0b; }}
    .stat-value.bad {{ color: #ef4444; }}
    .stat-label {{ color: #666; font-size: 0.875rem; margin-top: 0.25rem; }}
    .results {{ display: flex; flex-direction: column; gap: 0.75rem; }}
    .result {{ background: white; border-radius: 8px; overflow: hidden; }}
    .result-header {{ padding: 0.75rem 1rem; display: flex; align-items: center; gap: 0.75rem; cursor: pointer; }}
    .result-header:hover {{ background: #f9f9f9; }}
    .badge {{ padding: 0.2rem 0.6rem; border-radius: 999px; font-weight: 600; font-size: 0.7rem; }}
    .badge.pass {{ background: #dcfce7; color: #166534; }}
    .badge.fail {{ background: #fee2e2; color: #991b1b; }}
    .query {{ flex: 1; }}
    .latency {{ color: #666; font-size: 0.875rem; }}
    .details {{ display: none; padding: 1rem; border-top: 1px solid #eee; background: #fafafa; font-size: 0.875rem; }}
    .result.open .details {{ display: block; }}
    .metrics {{ display: flex; gap: 0.5rem; margin-bottom: 0.75rem; flex-wrap: wrap; }}
    .metric {{ background: #e5e7eb; padding: 0.25rem 0.5rem; border-radius: 4px; }}
    .metric.fail {{ background: #fee2e2; color: #991b1b; }}
    .failures {{ background: #fee2e2; padding: 0.5rem; border-radius: 4px; margin-bottom: 0.75rem; }}
    .failures li {{ margin-left: 1rem; color: #991b1b; }}
    .section {{ margin-bottom: 0.75rem; }}
    .section-title {{ font-weight: 600; margin-bottom: 0.25rem; }}
    .list {{ margin: 0; padding-left: 1.25rem; }}
    .answer {{ background: #f3f4f6; padding: 0.75rem; border-radius: 4px; white-space: pre-wrap; max-height: 150px; overflow-y: auto; }}
  </style>
</head>
<body>
  <h1>RAG Evaluation Report</h1>
  <div class="meta">
    <strong>{escape_html(folder)}</strong> &middot;
    {mode_label} RAG &middot;
    {total} items &middot;
    {datetime.now().strftime("%Y-%m-%d %H:%M")}
  </div>

  <div class="summary">
    <div class="stat">
      <div class="stat-value {stat_color(pass_rate)}">{pass_rate * 100:.0f}%</div>
      <div class="stat-label">Pass Rate</div>
    </div>
    <div class="stat">
      <div class="stat-value">{avg_doc_recall * 100:.0f}%</div>
      <div class="stat-label">Doc Recall</div>
    </div>
    <div class="stat">
      <div class="stat-value">{avg_citation_hit * 100:.0f}%</div>
      <div class="stat-label">Citation Hit</div>
    </div>
    <div class="stat">
      <div class="stat-value">{avg_tool_correct * 100:.0f}%</div>
      <div class="stat-label">Tool Correct</div>
    </div>
    <div class="stat">
      <div class="stat-value">{avg_latency:.0f}ms</div>
      <div class="stat-label">Avg Latency</div>
    </div>
  </div>

  <h2>Results</h2>
  <div class="results">{results_html}
  </div>
</body>
</html>"""


# =============================================================================
# CLI
# =============================================================================


async def main():
    parser = argparse.ArgumentParser(description="Run RAG evaluation on local documents")
    parser.add_argument("--folder", required=True, help="Path to folder with documents")
    parser.add_argument("-d", "--dataset", default="eval/dataset.json", help="Dataset JSON path")
    parser.add_argument("-o", "--out", default="eval/report.html", help="Output HTML path")
    parser.add_argument("-k", "--k-doc", type=int, default=10, help="K for retrieval")
    parser.add_argument(
        "--agent", action="store_true", help="Use full agentic RAG (requires database)"
    )
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        print(f"Folder not found: {folder}")
        sys.exit(1)

    # Load documents
    print(f"Loading documents from {folder}...")
    docs = await load_documents(folder)
    print(f"  Found {len(docs)} documents")

    if not docs:
        print("No documents found!")
        sys.exit(1)

    # Chunk documents using existing chunking service
    print("Chunking documents...")
    chunks = create_chunks(docs)
    print(f"  Created {len(chunks)} chunks")

    # Embed chunks using existing embedding service
    print("Embedding chunks...")
    await embed_chunks(chunks)
    print(f"  Embedded {len(chunks)} chunks")

    # Load dataset
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Dataset not found: {dataset_path}")
        sys.exit(1)

    print(f"\nLoading {dataset_path}...")
    dataset = EvalDataset.model_validate_json(dataset_path.read_text())
    print(f"Loaded {len(dataset.items)} eval items")
    print(f"Mode: {'Agent' if args.agent else 'Simple'} RAG\n")

    # Setup for agent mode
    folder_id = None
    user_id = None
    if args.agent:
        print("Setting up temporary folder in database...")
        folder_id, user_id = await setup_temp_folder(docs, chunks)
        print(f"  Created folder: {folder_id}\n")

    # Run evaluation
    results = []
    k = args.k_doc

    try:
        for i, item in enumerate(dataset.items):
            print(f"[{i + 1}/{len(dataset.items)}] {item.id}: {item.query[:60]}...")

            try:
                if args.agent:
                    response = await run_agent_rag(
                        query=item.query,
                        folder_id=folder_id,
                        user_id=user_id,
                    )
                else:
                    response = await run_simple_rag(
                        query=item.query,
                        chunks=chunks,
                        k=k,
                    )

                result = score_item(item, response, k)
                results.append(result)

                status = "\033[32mPASS\033[0m" if result.passed else "\033[31mFAIL\033[0m"
                print(f"  {status} ({response.latency_ms:.0f}ms)")
                for reason in result.failure_reasons:
                    print(f"    - {reason}")

            except Exception as e:
                print(f"  \033[31mERROR\033[0m: {e}")
                import traceback

                traceback.print_exc()
                results.append(
                    ItemResult(
                        item=item,
                        response=SystemResponse(
                            answer="", citations=[], tool_calls=[], retrieved=[], latency_ms=0
                        ),
                        doc_recall=0,
                        citation_hit=0,
                        tool_correct=0,
                        passed=False,
                        failure_reasons=[f"Error: {e}"],
                    )
                )

    finally:
        if args.agent and folder_id:
            print("\nCleaning up temporary folder...")
            await cleanup_temp_folder(folder_id)

    # Generate report
    html = generate_html_report(dataset, results, str(folder), args.agent)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)

    # Summary
    passed = sum(1 for r in results if r.passed)
    print(f"\n{'=' * 50}")
    print(f"Results: {passed}/{len(results)} passed ({passed / len(results) * 100:.0f}%)")
    print(f"Report: {out_path}")

    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
