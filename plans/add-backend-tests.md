# Plan: Add Backend Test Coverage

## Overview
Add comprehensive tests for backend services that lack coverage: `retrieval.py`, `drive.py`, `generation.py`, and `anthropic.py`.

## Test Convention
- **Location**: `backend/tests/unit/` for pure unit tests
- **Framework**: pytest with async support (`pytest.mark.asyncio`)
- **Mocking**: `unittest.mock.patch`, `AsyncMock` for async functions
- **Existing fixtures**: Use fixtures from `conftest.py` where applicable

---

## Existing Test Coverage

### Already Tested
| File | Test Location | Coverage |
|------|---------------|----------|
| `embedding.py` | `tests/unit/test_embedding.py` | Full |
| `chunking.py` | `tests/unit/test_chunking.py` | Full |
| `extraction.py` | `tests/test_extraction.py` | Partial |
| Routes (auth, chat, folders) | `tests/test_*.py` | Integration |

### Needs Tests
| File | Lines | Priority |
|------|-------|----------|
| `retrieval.py` | 173 | High |
| `drive.py` | 112 | High |
| `generation.py` | 78 | Medium |
| `anthropic.py` | 70 | Medium |

---

## Test Plans by Service

### 1. `tests/unit/test_retrieval.py`

#### `format_vector()`
```python
def test_format_vector_empty_list():
    """Empty list returns '[]'"""

def test_format_vector_single_element():
    """Single element: [0.5] -> '[0.5]'"""

def test_format_vector_multiple_elements():
    """Multiple elements formatted correctly"""

def test_format_vector_handles_scientific_notation():
    """Scientific notation floats preserved"""
```

#### `vector_search()`
```python
async def test_vector_search_returns_chunks_ordered_by_similarity():
    """Results ordered by descending similarity"""

async def test_vector_search_respects_top_k():
    """Returns at most top_k results"""

async def test_vector_search_filters_by_folder_id():
    """Only returns chunks from specified folder"""

async def test_vector_search_excludes_chunks_without_embeddings():
    """Chunks with NULL embeddings not returned"""

async def test_vector_search_returns_empty_for_empty_folder():
    """Empty folder returns empty list"""
```

#### `retrieve_and_rerank()`
```python
async def test_retrieve_and_rerank_two_stage_pipeline():
    """Vector search -> rerank pipeline works"""

async def test_retrieve_and_rerank_skips_rerank_when_few_candidates():
    """Skips reranking when candidates <= final_top_k"""

async def test_retrieve_and_rerank_returns_empty_for_no_matches():
    """Returns empty list when no vector matches"""

async def test_retrieve_and_rerank_sets_rerank_scores():
    """Chunks have rerank_score populated after reranking"""
```

#### `format_context_for_llm()`
```python
def test_format_context_empty_chunks():
    """Empty list returns empty string"""

def test_format_context_single_chunk():
    """Single chunk formatted with source marker"""

def test_format_context_multiple_chunks_separated():
    """Chunks separated by '---' delimiter"""

def test_format_context_includes_location():
    """Location info included when available"""
```

#### `_format_location()`
```python
def test_format_location_pdf_with_page():
    """PDF location shows 'Page N'"""

def test_format_location_doc_with_heading():
    """Doc location shows heading path"""

def test_format_location_empty_dict():
    """Empty dict returns empty string"""

def test_format_location_unknown_type():
    """Unknown type returns empty string"""
```

---

### 2. `tests/unit/test_drive.py`

#### `DriveService` Class
```python
class TestDriveServiceInit:
    def test_init_sets_auth_header():
        """Authorization header set from access token"""

    def test_drive_api_base_url():
        """Base URL is googleapis.com/drive/v3"""
```

#### `list_files()`
```python
async def test_list_files_returns_file_metadata():
    """Returns list of FileMetadata objects"""

async def test_list_files_handles_pagination():
    """Returns next_page_token when present"""

async def test_list_files_no_next_page():
    """Returns None for next_page_token when done"""

async def test_list_files_empty_folder():
    """Empty folder returns empty list"""

async def test_list_files_http_error():
    """Raises on HTTP error status"""
```

#### `get_file_metadata()`
```python
async def test_get_file_metadata_returns_single_file():
    """Returns FileMetadata for single file"""

async def test_get_file_metadata_includes_optional_fields():
    """Includes modifiedTime and size when present"""

async def test_get_file_metadata_not_found():
    """Raises on 404"""
```

#### `export_google_doc()`
```python
async def test_export_google_doc_returns_html():
    """Default export returns HTML content"""

async def test_export_google_doc_custom_mime_type():
    """Respects custom mime_type parameter"""

async def test_export_google_doc_http_error():
    """Raises on export failure"""
```

#### `download_file()`
```python
async def test_download_file_returns_bytes():
    """Returns raw file bytes"""

async def test_download_file_binary_content():
    """Handles binary PDF/image content"""

async def test_download_file_not_found():
    """Raises on 404"""
```

#### HTTP Client Singleton
```python
def test_get_http_client_singleton():
    """Returns same client instance"""

def test_http_client_timeout():
    """Client has 30s timeout configured"""
```

---

### 3. `tests/unit/test_generation.py`

#### `parse_citations()`
```python
def test_parse_citations_no_citations():
    """Text without citations returns single text segment"""

def test_parse_citations_single_citation():
    """Single [1] parsed correctly"""

def test_parse_citations_multiple_citations():
    """Multiple [1][2][3] all parsed"""

def test_parse_citations_excludes_array_indexing():
    """array[0] NOT parsed as citation"""

def test_parse_citations_text_before_and_after():
    """Text segments before and after citations preserved"""

def test_parse_citations_adjacent_citations():
    """[1][2] parsed as separate citations"""

def test_parse_citations_empty_string():
    """Empty string returns empty list"""

def test_parse_citations_multi_digit():
    """[10], [99], [123] work correctly"""

def test_parse_citations_mixed_content():
    """Mix of text, citations, array indexing"""
```

#### `extract_citation_numbers()`
```python
def test_extract_citation_numbers_basic():
    """Extracts {1, 2, 3} from text"""

def test_extract_citation_numbers_unique():
    """Duplicate citations return unique set"""

def test_extract_citation_numbers_excludes_arrays():
    """array[0] not included in results"""

def test_extract_citation_numbers_empty():
    """Empty text returns empty set"""

def test_extract_citation_numbers_no_citations():
    """Text without citations returns empty set"""
```

---

### 4. `tests/unit/test_anthropic.py`

#### `get_client()`
```python
def test_get_client_singleton():
    """Returns same client instance on multiple calls"""

def test_get_client_uses_api_key():
    """Client initialized with ANTHROPIC_API_KEY"""
```

#### `generate_stream()`
```python
async def test_generate_stream_yields_tokens():
    """Yields text chunks from stream"""

async def test_generate_stream_with_system_prompt():
    """Passes system prompt to API"""

async def test_generate_stream_custom_model():
    """Respects model parameter"""

async def test_generate_stream_custom_max_tokens():
    """Respects max_tokens parameter"""
```

#### `close_client()`
```python
async def test_close_client_resets_singleton():
    """After close, get_client creates new instance"""

async def test_close_client_idempotent():
    """Multiple close calls don't error"""
```

---

## Implementation Order

1. **`test_generation.py`** - Simplest, pure functions, no external deps
2. **`test_retrieval.py`** - Needs DB mocking but critical path
3. **`test_drive.py`** - HTTP mocking with httpx
4. **`test_anthropic.py`** - Streaming mock patterns

---

## Mocking Patterns

### Database (for retrieval.py)
```python
@pytest.fixture
async def mock_db_session():
    mock = AsyncMock(spec=AsyncSession)
    mock.execute.return_value = MagicMock(
        fetchall=lambda: [mock_row1, mock_row2]
    )
    return mock
```

### HTTP (for drive.py)
```python
@pytest.fixture
def mock_httpx_client():
    with patch("app.services.drive._get_http_client") as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client
```

### Anthropic Streaming
```python
class MockStream:
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        pass
    @property
    def text_stream(self):
        async def gen():
            for token in ["Hello", " ", "world"]:
                yield token
        return gen()
```

---

## Files to Create

| File | Tests | Est. Lines |
|------|-------|------------|
| `tests/unit/test_generation.py` | 14 | ~150 |
| `tests/unit/test_retrieval.py` | 14 | ~250 |
| `tests/unit/test_drive.py` | 14 | ~200 |
| `tests/unit/test_anthropic.py` | 7 | ~100 |
| **Total** | **49** | **~700** |

---

## Status
- [ ] `test_generation.py` (14 tests)
- [ ] `test_retrieval.py` (14 tests)
- [ ] `test_drive.py` (14 tests)
- [ ] `test_anthropic.py` (7 tests)
