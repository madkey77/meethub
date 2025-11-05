"""Unit tests for the vector store and embedding service abstractions."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Any, Iterable, cast

import pytest

from src.services.llm.base import LLMEmbeddingResult, LLMProvider


# ---- Shared configuration ----------------------------------------------------

@pytest.fixture(autouse=True)
def _ensure_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide mandatory settings so importing modules succeeds."""

    monkeypatch.setenv("DRIVE_ROOT_FOLDER_ID", "TEST-DRIVE-FOLDER-ID")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "TEST-DEEPGRAM-KEY")


# ---- Fake chromadb implementation -------------------------------------------


class _FakeCollection:
    def __init__(self, name: str, metadata: dict[str, Any] | None = None) -> None:
        self.name = name
        self.metadata = dict(metadata or {})
        self.upsert_calls: list[dict[str, Any]] = []
        self.query_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []
        self.query_response: dict[str, Any] = {
            "ids": [["a", "b"]],
            "metadatas": [[{"m": 1}, {"m": 2}]],
            "documents": [["doc-a", "doc-b"]],
            "distances": [[0.1, 0.2]],
        }

    def upsert(self, **kwargs: Any) -> None:
        self.upsert_calls.append(kwargs)

    def query(self, **kwargs: Any) -> dict[str, Any]:
        self.query_calls.append(kwargs)
        return self.query_response

    def delete(self, **kwargs: Any) -> None:
        self.delete_calls.append(kwargs)

    def modify(self, *, metadata: dict[str, Any]) -> None:  # pragma: no cover - exercised indirectly
        self.metadata = dict(metadata)


class _FakeNotFoundError(Exception):
    pass


class _FakePersistentClient:
    def __init__(self, *, path: str | None = None, **_: Any) -> None:
        self.path = path
        self.collections: dict[str, _FakeCollection] = {}
        self.delete_calls: list[str] = []
        self.persist_called = False

    def get_collection(self, name: str) -> _FakeCollection:
        if name not in self.collections:
            raise _FakeNotFoundError(name)
        return self.collections[name]

    def create_collection(
        self,
        *,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> _FakeCollection:
        collection = _FakeCollection(name=name, metadata=metadata)
        self.collections[name] = collection
        return collection

    def list_collections(self) -> list[_FakeCollection]:
        return list(self.collections.values())

    def delete_collection(self, name: str) -> None:
        if name not in self.collections:
            raise _FakeNotFoundError(name)
        self.delete_calls.append(name)
        del self.collections[name]

    def persist(self) -> None:
        self.persist_called = True


def _install_fake_chromadb(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject a synthetic chromadb module tree into sys.modules."""

    chromadb_mod = ModuleType("chromadb")
    setattr(chromadb_mod, "PersistentClient", _FakePersistentClient)

    errors_mod = ModuleType("chromadb.errors")
    setattr(errors_mod, "NotFoundError", _FakeNotFoundError)
    setattr(chromadb_mod, "errors", errors_mod)

    api_mod = ModuleType("chromadb.api")
    models_mod = ModuleType("chromadb.api.models")
    collection_mod = ModuleType("chromadb.api.models.Collection")

    class _CollectionType:  # pragma: no cover - import-time only
        pass

    setattr(collection_mod, "Collection", _CollectionType)
    setattr(models_mod, "Collection", collection_mod)
    setattr(api_mod, "models", models_mod)
    setattr(chromadb_mod, "api", api_mod)

    monkeypatch.setitem(sys.modules, "chromadb", chromadb_mod)
    monkeypatch.setitem(sys.modules, "chromadb.errors", errors_mod)
    monkeypatch.setitem(sys.modules, "chromadb.api", api_mod)
    monkeypatch.setitem(sys.modules, "chromadb.api.models", models_mod)
    monkeypatch.setitem(sys.modules, "chromadb.api.models.Collection", collection_mod)


def _load_vector_store(monkeypatch: pytest.MonkeyPatch):
    _install_fake_chromadb(monkeypatch)
    sys.modules.pop("src.services.vector_store", None)
    return importlib.import_module("src.services.vector_store")


# ---- ChromaVectorStore tests --------------------------------------------------


def test_vector_store_lazy_collection_and_metadata_merge(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    vs = _load_vector_store(monkeypatch)

    store = vs.ChromaVectorStore(
        persist_path=tmp_path,
        collection_name="unit_test",
        collection_metadata={"a": 1, "b": 2},
    )

    assert getattr(store, "_collection") is None

    collection = store.collection
    assert collection.name == "unit_test"
    assert collection.metadata == {"a": 1, "b": 2}

    client = cast(_FakePersistentClient, store.client)
    existing = client.get_collection("unit_test")
    existing.metadata = {"a": 1}

    ensured = store._ensure_collection("unit_test", {"a": 1, "b": 2})  # noqa: SLF001
    assert ensured.metadata == {"a": 1, "b": 2}


def test_vector_store_upsert_builds_payload(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    vs = _load_vector_store(monkeypatch)
    store = vs.ChromaVectorStore(persist_path=tmp_path, collection_name="c1")

    records = [
        vs.VectorRecord(vector_id="id1", values=[0.1, 0.2], metadata={"m": 1}, document="doc"),
        vs.VectorRecord(vector_id="id2", values=[0.3, 0.4], metadata=None, document=None),
    ]

    store.upsert(records)

    collection = cast(_FakePersistentClient, store.client).get_collection("c1")
    assert len(collection.upsert_calls) == 1
    payload = collection.upsert_calls[0]
    assert payload["ids"] == ["id1", "id2"]
    assert payload["embeddings"] == [[0.1, 0.2], [0.3, 0.4]]
    assert payload["metadatas"] == [{"m": 1}, {}]
    assert payload["documents"] == ["doc", ""]


def test_vector_store_query_returns_query_result(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    vs = _load_vector_store(monkeypatch)
    store = vs.ChromaVectorStore(persist_path=tmp_path, collection_name="c2")
    _ = store.collection  # force creation so fake client holds the collection
    collection = cast(_FakePersistentClient, store.client).get_collection("c2")

    collection.query_response = {
        "ids": [[1, 2]],
        "metadatas": [[None, {"x": None}]],
        "documents": [[None, "doc2"]],
        "distances": [[0, 1.23]],
    }

    result = store.query(vector=[0.5, 0.5], top_k=2, include_embeddings=True)
    assert result.ids == ["1", "2"]
    assert result.metadatas == [{}, {"x": None}]
    assert result.documents == ["", "doc2"]
    assert result.distances == [0.0, 1.23]

    call = collection.query_calls[-1]
    assert call["include"] == ["metadatas", "documents", "distances", "embeddings"]
    assert call["query_embeddings"] == [[0.5, 0.5]]
    assert call["n_results"] == 2


def test_vector_store_delete_requires_filter(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    vs = _load_vector_store(monkeypatch)
    store = vs.ChromaVectorStore(persist_path=tmp_path, collection_name="c3")

    with pytest.raises(ValueError):
        store.delete()

    store.delete(ids=["x"])
    collection = cast(_FakePersistentClient, store.client).get_collection("c3")
    assert collection.delete_calls[-1]["ids"] == ["x"]


def test_vector_store_list_reset_and_persist(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    vs = _load_vector_store(monkeypatch)
    store = vs.ChromaVectorStore(persist_path=tmp_path, collection_name="c4")
    client = cast(_FakePersistentClient, store.client)

    _ = store.collection
    assert store.list_collections() == ["c4"]

    store.persist()
    assert client.persist_called is True

    store.reset_collection()
    assert client.delete_calls[-1] == "c4"
    assert "c4" in client.collections


# ---- Embedding service tests -------------------------------------------------


class _FakeLLMProvider(LLMProvider):
    def __init__(
        self,
        *,
        name: str,
        chat_model: str = "chat",
        embedding_model: str | None = "embed",
    ) -> None:
        super().__init__(chat_model=chat_model, embedding_model=embedding_model)
        self._name = name
        self.embed_calls: list[list[str]] = []

    @property
    def provider_name(self) -> str:
        return self._name

    def generate(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - unused
        raise NotImplementedError

    def embed(self, texts: Iterable[str]) -> LLMEmbeddingResult:
        payload = list(texts)
        self.embed_calls.append(payload)
        return LLMEmbeddingResult(
            vectors=[[float(i)] for i, _ in enumerate(payload, start=1)],
            model=self.embedding_model_name or self.model_name,
            provider=self.provider_name,
        )

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int = 0) -> float:  # pragma: no cover
        return 0.0


class _FakeLLMFactory:
    last_provider: _FakeLLMProvider | None = None

    @classmethod
    def create(
        cls,
        provider_name: str | None = None,
        *,
        overrides: dict[str, Any] | None = None,
    ) -> _FakeLLMProvider:
        resolved = (provider_name or "openai").lower()
        embedding_model = overrides.get("embedding_model") if overrides else "embed"
        provider = _FakeLLMProvider(name=resolved, embedding_model=embedding_model)
        cls.last_provider = provider
        return provider


def test_embedding_service_register_and_get_provider() -> None:
    from src.services.embedding.base import EmbeddingService

    svc = EmbeddingService(default_provider="openai", factory=_FakeLLMFactory)  # type: ignore[arg-type]
    provider = _FakeLLMProvider(name="OpenAI")
    svc.register_provider("OpenAI", provider)

    retrieved = svc.get_provider("OPENAI")
    assert retrieved is provider
    assert svc.available_providers() == ["openai"]


def test_embedding_service_lazy_factory_and_embed_round_trip() -> None:
    from src.services.embedding.base import EmbeddingService

    svc = EmbeddingService(default_provider="anthropic", factory=_FakeLLMFactory)  # type: ignore[arg-type]
    provider = svc.get_provider()
    assert provider.provider_name == "anthropic"

    batch = svc.embed(["one", "two"])
    assert batch.provider == "anthropic"
    assert len(batch.vectors) == 2
    assert _FakeLLMFactory.last_provider is not None
    assert _FakeLLMFactory.last_provider.embed_calls[-1] == ["one", "two"]


def test_llm_embedding_adapter_requires_embedding_model() -> None:
    from src.services.embedding.base import LLMEmbeddingAdapter
    from src.utils.exceptions import ConfigurationError

    llm = _FakeLLMProvider(name="openai", embedding_model=None)
    with pytest.raises(ConfigurationError):
        LLMEmbeddingAdapter(llm)


def test_llm_embedding_adapter_wraps_not_implemented() -> None:
    from src.services.embedding.base import LLMEmbeddingAdapter
    from src.utils.exceptions import ConfigurationError

    class _NoEmbedProvider(_FakeLLMProvider):
        def embed(self, texts: Iterable[str]) -> LLMEmbeddingResult:  # type: ignore[override]
            raise NotImplementedError

    adapter = LLMEmbeddingAdapter(_NoEmbedProvider(name="openai"))
    with pytest.raises(ConfigurationError):
        adapter.embed(["x"])


def test_llm_embedding_adapter_empty_texts_returns_empty_batch() -> None:
    from src.services.embedding.base import LLMEmbeddingAdapter

    adapter = LLMEmbeddingAdapter(_FakeLLMProvider(name="openai"))
    batch = adapter.embed([])
    assert batch.vectors == []
    assert batch.provider == "openai"
