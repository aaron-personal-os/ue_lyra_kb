#!/usr/bin/env python3
"""wiki_embeddings.py — ProjectWiki v2.0 Embedding Provider Abstraction

Supports multiple embedding providers via config.yaml.
Uses only urllib.request (stdlib) for HTTP — NO external dependencies.

Config in ProjectWiki/_schema/config.yaml:
  retrieval:
    embedding:
      provider: openai | ollama | custom
      api_url: "https://api.openai.com/v1/embeddings"
      api_key_env: "OPENAI_API_KEY"
      model: "text-embedding-3-small"
      dimensions: 1536
      batch_size: 50

Chunking Strategy (v2.0):
  - Each page -> 1 chunk = compiled_summary + first 500 words of body
  - If page > 1000 words -> 2 chunks (first 500 + next 500)
  - Chunk text is what gets embedded
"""

from __future__ import annotations

import json
import os
import struct
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class EmbeddingConfig:
    """Embedding provider configuration."""
    provider: str = "openai"
    api_url: str = "https://api.openai.com/v1/embeddings"
    api_key_env: str = "OPENAI_API_KEY"
    model: str = "text-embedding-3-small"
    dimensions: int = 1536
    batch_size: int = 50

    @classmethod
    def from_dict(cls, d: dict) -> EmbeddingConfig:
        """Create from config dict (parsed YAML)."""
        return cls(
            provider=d.get("provider", "openai"),
            api_url=d.get("api_url", "https://api.openai.com/v1/embeddings"),
            api_key_env=d.get("api_key_env", "OPENAI_API_KEY"),
            model=d.get("model", "text-embedding-3-small"),
            dimensions=int(d.get("dimensions", 1536)),
            batch_size=int(d.get("batch_size", 50)),
        )


@dataclass
class Chunk:
    """A text chunk derived from a wiki page, ready for embedding."""
    page_id: str
    chunk_index: int
    chunk_text: str
    token_count: int  # approximate


# ---------------------------------------------------------------------------
# Chunking Logic
# ---------------------------------------------------------------------------

def _word_split(text: str) -> list[str]:
    """Split text into word-level tokens (simple whitespace split)."""
    return text.split()


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~1.3x word count for English, ~2x for CJK-heavy."""
    words = _word_split(text)
    # Check if CJK-heavy
    cjk_chars = sum(1 for c in text if '一' <= c <= '鿿')
    if cjk_chars > len(text) * 0.3:
        return int(len(words) * 2.0)
    return int(len(words) * 1.3)


def chunk_page(page_id: str, compiled_summary: str, body_text: str,
               max_words_per_chunk: int = 500) -> list[Chunk]:
    """Split a wiki page into chunks for embedding.

    Strategy:
      - Chunk 0: compiled_summary + first max_words_per_chunk words of body
      - Chunk 1 (if body > 1000 words): next max_words_per_chunk words

    Args:
        page_id: Page identifier
        compiled_summary: The page's compiled_summary field
        body_text: The page body (frontmatter stripped)
        max_words_per_chunk: Max words per chunk

    Returns:
        List of Chunk objects (1 or 2 per page)
    """
    chunks: list[Chunk] = []

    # Prepare body words
    body_words = _word_split(body_text)

    # Chunk 0: summary + first N words
    prefix = compiled_summary.strip()
    if prefix:
        prefix += "\n\n"
    first_section = " ".join(body_words[:max_words_per_chunk])
    chunk0_text = (prefix + first_section).strip()

    if chunk0_text:
        chunks.append(Chunk(
            page_id=page_id,
            chunk_index=0,
            chunk_text=chunk0_text,
            token_count=_estimate_tokens(chunk0_text),
        ))

    # Chunk 1: if body has > 1000 words, take next 500
    if len(body_words) > 1000:
        second_section = " ".join(body_words[max_words_per_chunk:max_words_per_chunk * 2])
        if second_section.strip():
            chunks.append(Chunk(
                page_id=page_id,
                chunk_index=1,
                chunk_text=second_section.strip(),
                token_count=_estimate_tokens(second_section),
            ))

    return chunks


# ---------------------------------------------------------------------------
# Embedding Providers
# ---------------------------------------------------------------------------

class EmbeddingProvider:
    """Base class for embedding providers."""

    def __init__(self, config: EmbeddingConfig):
        self.config = config

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns list of embedding vectors."""
        raise NotImplementedError

    def embed_one(self, text: str) -> list[float]:
        """Embed a single text. Returns one embedding vector."""
        results = self.embed([text])
        if results:
            return results[0]
        return []

    def is_available(self) -> tuple[bool, str]:
        """Check if provider is available (API key set, server reachable, etc.).

        Returns: (available, reason_if_not)
        """
        return True, ""


class OpenAIProvider(EmbeddingProvider):
    """OpenAI-compatible API provider.

    Works with: OpenAI, Azure OpenAI, DeepSeek, any OpenAI-compatible endpoint.
    Uses urllib.request (stdlib) for HTTP calls.
    """

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self._api_key: Optional[str] = None

    def _get_api_key(self) -> str:
        """Get API key from environment variable."""
        if self._api_key is None:
            self._api_key = os.environ.get(self.config.api_key_env, "")
        return self._api_key

    def is_available(self) -> tuple[bool, str]:
        key = self._get_api_key()
        if not key:
            return False, f"Environment variable {self.config.api_key_env} not set"
        return True, ""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Call OpenAI embeddings API."""
        api_key = self._get_api_key()
        if not api_key:
            raise RuntimeError(
                f"API key not found: set environment variable {self.config.api_key_env}"
            )

        url = self.config.api_url
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        payload: dict = {
            "input": texts,
            "model": self.config.model,
        }
        # Only include dimensions if the model supports it
        if self.config.dimensions and "text-embedding-3" in self.config.model:
            payload["dimensions"] = self.config.dimensions

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            raise RuntimeError(
                f"OpenAI API error {e.code}: {error_body[:200]}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Cannot reach embedding API at {url}: {e.reason}") from e

        # Parse response
        embeddings_data = body.get("data", [])
        # Sort by index to ensure correct order
        embeddings_data.sort(key=lambda x: x.get("index", 0))
        return [item["embedding"] for item in embeddings_data]


class OllamaProvider(EmbeddingProvider):
    """Local Ollama server (http://localhost:11434/api/embed).

    No API key needed — runs on local machine.
    """

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        # Default Ollama URL if not specified
        if not config.api_url or "openai.com" in config.api_url:
            config.api_url = "http://localhost:11434/api/embed"

    def is_available(self) -> tuple[bool, str]:
        """Check if Ollama is running."""
        try:
            req = urllib.request.Request(
                self.config.api_url.replace("/api/embed", "/api/tags"),
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5):
                pass
            return True, ""
        except Exception as e:
            return False, f"Ollama not reachable: {e}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Call Ollama embed API (batch supported in newer versions)."""
        url = self.config.api_url
        headers = {"Content-Type": "application/json"}

        # Ollama /api/embed supports batch via "input" field
        payload = {
            "model": self.config.model,
            "input": texts,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            raise RuntimeError(
                f"Ollama API error {e.code}: {error_body[:200]}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Cannot reach Ollama at {url}: {e.reason}"
            ) from e

        # Ollama returns {"embeddings": [[...], [...]]}
        embeddings = body.get("embeddings", [])
        if not embeddings:
            # Fallback: older Ollama returns {"embedding": [...]} for single
            single = body.get("embedding", [])
            if single:
                embeddings = [single]

        return embeddings


class CustomProvider(OpenAIProvider):
    """Any OpenAI-compatible endpoint with custom URL.

    Same as OpenAI but uses the api_url from config as-is.
    Useful for self-hosted models, vLLM, LocalAI, etc.
    """
    pass


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_provider(config: EmbeddingConfig) -> EmbeddingProvider:
    """Create an embedding provider based on config.

    Args:
        config: EmbeddingConfig with provider type and settings

    Returns:
        EmbeddingProvider instance
    """
    provider_map = {
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
        "custom": CustomProvider,
    }

    cls = provider_map.get(config.provider, OpenAIProvider)
    return cls(config)


# ---------------------------------------------------------------------------
# Batch Embedding Helper
# ---------------------------------------------------------------------------

def embed_chunks_batched(
    provider: EmbeddingProvider,
    chunks: list[Chunk],
    batch_size: int = 50,
    on_progress: Optional[callable] = None,
) -> list[tuple[Chunk, list[float]]]:
    """Embed chunks in batches, returning (chunk, embedding) pairs.

    Args:
        provider: The embedding provider to use
        chunks: List of Chunk objects to embed
        batch_size: How many texts to send per API call
        on_progress: Optional callback(done_count, total_count)

    Returns:
        List of (Chunk, embedding_vector) tuples.
        Chunks that failed to embed are excluded.
    """
    results: list[tuple[Chunk, list[float]]] = []
    total = len(chunks)

    for i in range(0, total, batch_size):
        batch = chunks[i:i + batch_size]
        texts = [c.chunk_text for c in batch]

        try:
            embeddings = provider.embed(texts)
        except RuntimeError as e:
            print(f"  [warn] Batch {i // batch_size + 1} failed: {e}", file=sys.stderr)
            continue

        for chunk, embedding in zip(batch, embeddings):
            results.append((chunk, embedding))

        if on_progress:
            on_progress(min(i + batch_size, total), total)

    return results


# ---------------------------------------------------------------------------
# Vector Serialization (for sqlite-vec)
# ---------------------------------------------------------------------------

def embedding_to_blob(embedding: list[float]) -> bytes:
    """Convert embedding list[float] to raw float32 bytes for sqlite-vec."""
    return struct.pack(f"{len(embedding)}f", *embedding)


def blob_to_embedding(blob: bytes, dimensions: int) -> list[float]:
    """Convert raw float32 bytes back to list[float]."""
    return list(struct.unpack(f"{dimensions}f", blob))


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Basic chunking test
    print("=== Chunking Test ===")
    test_summary = "This page describes the ability system architecture."
    test_body = " ".join([f"word{i}" for i in range(1200)])

    chunks = chunk_page("programming/ability-system/overview", test_summary, test_body)
    print(f"  Chunks generated: {len(chunks)}")
    for c in chunks:
        print(f"  - chunk[{c.chunk_index}]: {c.token_count} tokens, "
              f"text[:50]={c.chunk_text[:50]!r}...")

    # Provider availability test
    print("\n=== Provider Availability ===")
    cfg = EmbeddingConfig()
    provider = create_provider(cfg)
    avail, reason = provider.is_available()
    print(f"  Provider={cfg.provider}, available={avail}, reason={reason or 'OK'}")

    # Serialization test
    print("\n=== Serialization Test ===")
    test_vec = [0.1, 0.2, 0.3, 0.4, 0.5]
    blob = embedding_to_blob(test_vec)
    roundtrip = blob_to_embedding(blob, 5)
    assert all(abs(a - b) < 1e-6 for a, b in zip(test_vec, roundtrip))
    print(f"  Roundtrip OK: {len(blob)} bytes for {len(test_vec)}-dim vector")

    print("\nAll tests passed.")
