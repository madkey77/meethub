"""RAG Pipeline orchestration service coordinating all RAG operations.

This module provides the main RAG pipeline orchestrator that coordinates:
- Content normalization
- Text chunking with metadata preservation
- Embedding generation
- Vector store updates
- Artifact generation

The pipeline tracks execution via JobRun and JobStep entities for observability
and supports retry logic for resilient processing.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.config import settings
from src.models import (
    Artifact,
    ArtifactLink,
    ArtifactVersion,
    Chunk,
    Embedding,
    FileVersion,
    JobRun,
    JobRunStatus,
    JobStep,
    JobStepStatus,
    LinkRoleType,
)
from src.services.artifact_generation.base import ArtifactGenerator, ArtifactResult
from src.services.chunking.base import ChunkingStrategy, ChunkResult
from src.services.embedding.base import EmbeddingBatch, EmbeddingService
from src.services.llm.base import LLMProvider
from src.services.llm.factory import LLMProviderFactory
from src.services.vector_store import ChromaVectorStore, VectorRecord
from src.utils.exceptions import (
    ArtifactGenerationError,
    ChunkingError,
    EmbeddingError,
    LLMProviderError,
    RAGError,
    VectorStoreError,
)
from src.utils.logging import get_logger


class RAGPipeline:
    """RAG pipeline orchestrator coordinating normalize → chunk → embed → generate_artifacts.

    This is the main entry point for RAG operations. It coordinates all steps
    of the RAG pipeline and tracks execution state via JobRun and JobStep entities.

    Example:
        >>> from src.models import SessionLocal
        >>> from src.services.rag_pipeline import RAGPipeline
        >>>
        >>> db = SessionLocal()
        >>> pipeline = RAGPipeline(db)
        >>>
        >>> # Process a file version through the RAG pipeline
        >>> rules = {
        ...     "chunking_strategy": "MeetingChunker",
        ...     "chunk_size": 1200,
        ...     "chunk_overlap": 200,
        ...     "embedding_provider": "openai",
        ...     "embedding_model": "text-embedding-3-large",
        ...     "artifacts": [
        ...         {
        ...             "kind": "summary",
        ...             "generator": "SummaryGenerator",
        ...             "llm_provider": "openai",
        ...             "llm_model": "gpt-4o"
        ...         }
        ...     ]
        ... }
        >>>
        >>> job_run = pipeline.process_file(file_version, rules)
        >>> print(f"Job status: {job_run.status}")
    """

    def __init__(
        self,
        db_session: Session,
        *,
        vector_store: Optional[ChromaVectorStore] = None,
        embedding_service: Optional[EmbeddingService] = None,
        llm_factory: Optional[type[LLMProviderFactory]] = None,
    ) -> None:
        """Initialize RAG pipeline with database session and optional dependencies.

        Args:
            db_session: SQLAlchemy database session for persistence
            vector_store: ChromaDB vector store instance (defaults to new instance)
            embedding_service: Embedding service instance (defaults to new instance)
            llm_factory: LLM provider factory (defaults to LLMProviderFactory)
        """
        self._db = db_session
        self._logger = get_logger(__name__).bind(service="rag_pipeline")
        self._vector_store = vector_store or ChromaVectorStore()
        self._embedding_service = embedding_service or EmbeddingService()
        self._llm_factory = llm_factory or LLMProviderFactory

    def process_file(
        self,
        file_version: FileVersion,
        rules: Dict[str, Any],
    ) -> JobRun:
        """Process a file version through the complete RAG pipeline.

        This is the main entry point for RAG processing. It coordinates all pipeline
        steps and returns a JobRun tracking execution state.

        Pipeline flow:
            1. Create JobRun with status='queued'
            2. Normalize content (remove excessive whitespace, etc.)
            3. Chunk content with metadata preservation
            4. Generate embeddings for chunks
            5. Store embeddings in vector store
            6. Generate artifacts (summaries, entities, decisions, etc.)
            7. Update JobRun status to 'success', 'failed', or 'partial'

        Args:
            file_version: FileVersion entity to process
            rules: Processing rules dictionary containing:
                - chunking_strategy: Strategy name (e.g., "MeetingChunker")
                - chunk_size: Character length for chunks
                - chunk_overlap: Character overlap between chunks
                - embedding_provider: Provider name (e.g., "openai")
                - embedding_model: Model name (e.g., "text-embedding-3-large")
                - artifacts: List of artifact generation configs

        Returns:
            JobRun entity tracking pipeline execution

        Raises:
            RAGError: If critical pipeline steps fail (normalize, chunk, embed)

        Example:
            >>> rules = {
            ...     "chunking_strategy": "DocumentChunker",
            ...     "chunk_size": 1200,
            ...     "chunk_overlap": 200,
            ...     "embedding_provider": "openai",
            ...     "artifacts": [{"kind": "summary", "llm_provider": "openai"}]
            ... }
            >>> job_run = pipeline.process_file(file_version, rules)
        """
        pipeline_name = rules.get("pipeline_name", "default-rag-pipeline")

        # Create JobRun to track execution
        job_run = self._create_job_run(
            file_version_id=file_version.version_id,
            pipeline_name=pipeline_name,
        )

        self._logger.info(
            "rag_pipeline.start",
            job_id=job_run.job_id,
            file_version_id=file_version.version_id,
            pipeline_name=pipeline_name,
        )

        try:
            # Update status to running
            job_run.status = JobRunStatus.RUNNING
            job_run.started_at = datetime.utcnow()
            self._db.commit()

            # Step 1: Normalize content
            normalized_content = self._normalize_content_step(job_run, file_version, rules)

            # Step 2: Chunk content
            chunk_results = self._chunk_content_step(
                job_run, normalized_content, file_version, rules
            )

            # Step 3: Generate embeddings
            embedding_batch = self._generate_embeddings_step(job_run, chunk_results, rules)

            # Step 4: Store chunks and embeddings
            self._store_chunks_and_embeddings(
                job_run, file_version, chunk_results, embedding_batch, rules
            )

            # Step 5: Generate artifacts (non-critical - failures result in 'partial')
            artifacts_produced = self._generate_artifacts_step(
                job_run, file_version, normalized_content, rules
            )

            # Calculate final metrics
            metrics = {
                "input_file_count": 1,
                "chunks_created": len(chunk_results),
                "embeddings_generated": len(embedding_batch.vectors),
                "artifacts_produced": artifacts_produced,
                "duration_seconds": (datetime.utcnow() - job_run.started_at).total_seconds(),
                "embedding_provider": rules.get("embedding_provider", "openai"),
                "embedding_model": rules.get("embedding_model", settings.openai_embedding_model),
            }

            # Update job with success status
            job_run.status = JobRunStatus.SUCCESS
            job_run.completed_at = datetime.utcnow()
            job_run.metrics = metrics
            self._db.commit()

            self._logger.info(
                "rag_pipeline.complete",
                job_id=job_run.job_id,
                status=job_run.status.value,
                metrics=metrics,
            )

            return job_run

        except (ChunkingError, EmbeddingError, VectorStoreError) as e:
            # Critical errors - mark as failed
            job_run.status = JobRunStatus.FAILED
            job_run.completed_at = datetime.utcnow()
            self._db.commit()

            self._logger.error(
                "rag_pipeline.failed",
                job_id=job_run.job_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

        except ArtifactGenerationError as e:
            # Non-critical error - embeddings succeeded, mark as partial
            job_run.status = JobRunStatus.PARTIAL
            job_run.completed_at = datetime.utcnow()
            self._db.commit()

            self._logger.warning(
                "rag_pipeline.partial",
                job_id=job_run.job_id,
                error=str(e),
                reason="Artifact generation failed but embeddings succeeded",
            )
            return job_run

        except Exception as e:
            # Unexpected error
            job_run.status = JobRunStatus.FAILED
            job_run.completed_at = datetime.utcnow()
            self._db.commit()

            self._logger.error(
                "rag_pipeline.unexpected_error",
                job_id=job_run.job_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise RAGError(
                f"Unexpected error in RAG pipeline: {str(e)}",
                details={"job_id": job_run.job_id, "error_type": type(e).__name__},
            ) from e

    def _normalize_content_step(
        self, job_run: JobRun, file_version: FileVersion, rules: Dict[str, Any]
    ) -> str:
        """Execute content normalization step with tracking.

        Args:
            job_run: JobRun tracking this pipeline execution
            file_version: FileVersion to normalize
            rules: Processing rules

        Returns:
            Normalized content string

        Raises:
            RAGError: If content cannot be read or normalized
        """
        step = self._create_job_step(job_run, "normalize")

        try:
            step.status = JobStepStatus.RUNNING
            step.started_at = datetime.utcnow()
            self._db.commit()

            # Read content from file version
            # In production, this would read from content_locator
            # For now, assume content is accessible
            content = self._read_file_content(file_version)

            # Normalize: remove excessive whitespace, normalize line endings
            normalized = self._normalize_content(content)

            # Log step output
            step.log_output = {
                "original_length": len(content),
                "normalized_length": len(normalized),
                "removed_chars": len(content) - len(normalized),
            }
            step.status = JobStepStatus.SUCCESS
            step.completed_at = datetime.utcnow()
            self._db.commit()

            return normalized

        except Exception as e:
            step.status = JobStepStatus.FAILED
            step.error_message = str(e)
            step.error_type = type(e).__name__
            step.completed_at = datetime.utcnow()
            self._db.commit()

            raise RAGError(
                f"Content normalization failed: {str(e)}",
                details={"file_version_id": file_version.version_id},
            ) from e

    def _chunk_content_step(
        self,
        job_run: JobRun,
        content: str,
        file_version: FileVersion,
        rules: Dict[str, Any],
    ) -> List[ChunkResult]:
        """Execute chunking step with tracking.

        Args:
            job_run: JobRun tracking this pipeline execution
            content: Normalized content to chunk
            file_version: Source FileVersion for metadata
            rules: Processing rules with chunking configuration

        Returns:
            List of ChunkResult objects

        Raises:
            ChunkingError: If chunking fails
        """
        step = self._create_job_step(job_run, "chunk")

        try:
            step.status = JobStepStatus.RUNNING
            step.started_at = datetime.utcnow()
            self._db.commit()

            # Get chunking strategy from rules
            strategy_name = rules.get("chunking_strategy", "DocumentChunker")
            chunk_size = rules.get("chunk_size", settings.rag_chunk_size)
            chunk_overlap = rules.get("chunk_overlap", settings.rag_chunk_overlap)

            # Import and instantiate strategy dynamically
            # This would use a strategy registry in production
            from src.services.chunking.document_chunker import DocumentChunker
            from src.services.chunking.meeting_chunker import MeetingChunker

            strategy_map = {
                "DocumentChunker": DocumentChunker,
                "MeetingChunker": MeetingChunker,
            }

            if strategy_name not in strategy_map:
                raise ChunkingError(
                    f"Unknown chunking strategy: {strategy_name}",
                    details={"available": list(strategy_map.keys())},
                )

            strategy_class = strategy_map[strategy_name]
            strategy: ChunkingStrategy = strategy_class(
                chunk_size=chunk_size, chunk_overlap=chunk_overlap
            )

            # Execute chunking
            chunk_results = strategy.chunk(content)

            # Log step output
            step.log_output = {
                "strategy": strategy_name,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "chunks_created": len(chunk_results),
                "total_chars": sum(len(c.text_content) for c in chunk_results),
            }
            step.status = JobStepStatus.SUCCESS
            step.completed_at = datetime.utcnow()
            self._db.commit()

            return chunk_results

        except Exception as e:
            step.status = JobStepStatus.FAILED
            step.error_message = str(e)
            step.error_type = type(e).__name__
            step.completed_at = datetime.utcnow()
            self._db.commit()

            raise ChunkingError(
                f"Chunking failed: {str(e)}",
                details={"file_version_id": file_version.version_id, "strategy": strategy_name},
            ) from e

    def _generate_embeddings_step(
        self, job_run: JobRun, chunk_results: List[ChunkResult], rules: Dict[str, Any]
    ) -> EmbeddingBatch:
        """Execute embedding generation step with tracking.

        Args:
            job_run: JobRun tracking this pipeline execution
            chunk_results: List of chunks to embed
            rules: Processing rules with embedding configuration

        Returns:
            EmbeddingBatch with generated vectors

        Raises:
            EmbeddingError: If embedding generation fails
        """
        step = self._create_job_step(job_run, "embed")

        try:
            step.status = JobStepStatus.RUNNING
            step.started_at = datetime.utcnow()
            self._db.commit()

            # Extract text from chunks
            texts = [chunk.text_content for chunk in chunk_results]

            # Get embedding configuration
            provider_name = rules.get("embedding_provider", settings.llm_provider_preference)

            # Generate embeddings
            embedding_batch = self._embedding_service.embed(texts, provider_name=provider_name)

            # Log step output
            step.log_output = {
                "provider": embedding_batch.provider,
                "model": embedding_batch.model,
                "chunks_embedded": len(texts),
                "vector_dimension": len(embedding_batch.vectors[0]) if embedding_batch.vectors else 0,
            }
            step.status = JobStepStatus.SUCCESS
            step.completed_at = datetime.utcnow()
            self._db.commit()

            return embedding_batch

        except Exception as e:
            step.status = JobStepStatus.FAILED
            step.error_message = str(e)
            step.error_type = type(e).__name__
            step.completed_at = datetime.utcnow()
            self._db.commit()

            raise EmbeddingError(
                f"Embedding generation failed: {str(e)}",
                details={"chunk_count": len(chunk_results), "provider": provider_name},
            ) from e

    def _store_chunks_and_embeddings(
        self,
        job_run: JobRun,
        file_version: FileVersion,
        chunk_results: List[ChunkResult],
        embedding_batch: EmbeddingBatch,
        rules: Dict[str, Any],
    ) -> None:
        """Store chunks in database and embeddings in vector store.

        This is not a separate step in the pipeline, but part of the embedding step.
        It stores both the chunk metadata in the database and the vectors in ChromaDB.

        Args:
            job_run: JobRun tracking this pipeline execution
            file_version: Source FileVersion
            chunk_results: List of chunks to store
            embedding_batch: Embedding vectors from LLM provider
            rules: Processing rules

        Raises:
            VectorStoreError: If vector store operations fail
        """
        try:
            # Store chunks in database
            for idx, (chunk_result, vector) in enumerate(zip(chunk_results, embedding_batch.vectors)):
                # Create Chunk entity
                chunk = Chunk(
                    file_version_id=file_version.version_id,
                    chunk_index=chunk_result.chunk_index,
                    text_content=chunk_result.text_content,
                    char_offset_start=chunk_result.char_offset_start,
                    char_offset_end=chunk_result.char_offset_end,
                    metadata=chunk_result.metadata,
                    deleted=False,
                )
                self._db.add(chunk)
                self._db.flush()  # Get chunk_id

                # Create Embedding entity
                vector_db_id = f"chunk_{chunk.chunk_id}"
                collection_name = f"file_{file_version.file_id}"

                embedding = Embedding(
                    chunk_id=chunk.chunk_id,
                    embedding_model=embedding_batch.model,
                    vector_db_id=vector_db_id,
                    collection_name=collection_name,
                )
                self._db.add(embedding)

                # Store in ChromaDB
                vector_record = VectorRecord(
                    vector_id=vector_db_id,
                    values=vector,
                    metadata={
                        "chunk_id": chunk.chunk_id,
                        "file_version_id": file_version.version_id,
                        "chunk_index": chunk_result.chunk_index,
                        **(chunk_result.metadata or {}),
                    },
                    document=chunk_result.text_content,
                )

                # Upsert to vector store (batching would be more efficient in production)
                self._vector_store.upsert([vector_record])

            self._db.commit()

            self._logger.info(
                "rag_pipeline.chunks_stored",
                job_id=job_run.job_id,
                chunks_stored=len(chunk_results),
                collection=collection_name,
            )

        except Exception as e:
            self._db.rollback()
            raise VectorStoreError(
                f"Failed to store chunks and embeddings: {str(e)}",
                details={"chunk_count": len(chunk_results)},
            ) from e

    def _generate_artifacts_step(
        self,
        job_run: JobRun,
        file_version: FileVersion,
        content: str,
        rules: Dict[str, Any],
    ) -> int:
        """Execute artifact generation step with tracking.

        This step is non-critical - failures will result in 'partial' job status
        rather than 'failed', since embeddings have already succeeded.

        Args:
            job_run: JobRun tracking this pipeline execution
            file_version: Source FileVersion
            content: Normalized content for artifact generation
            rules: Processing rules with artifact configurations

        Returns:
            Number of artifacts successfully generated

        Raises:
            ArtifactGenerationError: If artifact generation fails
        """
        artifacts_config = rules.get("artifacts", [])
        if not artifacts_config:
            self._logger.info("rag_pipeline.no_artifacts", job_id=job_run.job_id)
            return 0

        artifacts_produced = 0
        llm_tokens_total = 0
        llm_cost_total = 0.0

        for artifact_config in artifacts_config:
            artifact_kind = artifact_config.get("kind")
            step_name = f"generate_{artifact_kind}"
            step = self._create_job_step(job_run, step_name)

            try:
                step.status = JobStepStatus.RUNNING
                step.started_at = datetime.utcnow()
                self._db.commit()

                # Get artifact generator
                generator_class = ArtifactGenerator.get_generator(artifact_kind)
                generator = generator_class()

                # Get LLM provider
                llm_provider_name = artifact_config.get(
                    "llm_provider", settings.llm_provider_preference
                )
                llm_model = artifact_config.get(
                    "llm_model",
                    settings.openai_chat_model
                    if llm_provider_name == "openai"
                    else settings.anthropic_chat_model,
                )

                llm_provider: LLMProvider = self._llm_factory.create(
                    llm_provider_name, chat_model=llm_model
                )

                # Generate artifact
                artifact_result: ArtifactResult = generator.generate(
                    context=content,
                    llm_provider=llm_provider,
                    source_type="file",
                    file_version_id=file_version.version_id,
                )

                # Store artifact
                self._store_artifact(job_run, file_version, artifact_result)

                # Update metrics
                tokens_used = (
                    artifact_result.metadata.get("prompt_tokens", 0)
                    + artifact_result.metadata.get("completion_tokens", 0)
                )
                llm_tokens_total += tokens_used
                llm_cost_total += artifact_result.metadata.get("cost_estimate", 0.0)

                # Log step success
                step.log_output = {
                    "artifact_kind": artifact_kind,
                    "llm_provider": llm_provider_name,
                    "llm_model": llm_model,
                    "tokens_used": tokens_used,
                    "cost_estimate": artifact_result.metadata.get("cost_estimate", 0.0),
                }
                step.status = JobStepStatus.SUCCESS
                step.completed_at = datetime.utcnow()
                self._db.commit()

                artifacts_produced += 1

            except Exception as e:
                step.status = JobStepStatus.FAILED
                step.error_message = str(e)
                step.error_type = type(e).__name__
                step.completed_at = datetime.utcnow()
                self._db.commit()

                self._logger.error(
                    "rag_pipeline.artifact_failed",
                    job_id=job_run.job_id,
                    artifact_kind=artifact_kind,
                    error=str(e),
                )

                # Continue with other artifacts even if one fails
                continue

        # Update job metrics with LLM usage
        if job_run.metrics:
            job_run.metrics["llm_tokens_used"] = llm_tokens_total
            job_run.metrics["llm_cost_estimate"] = llm_cost_total
            self._db.commit()

        return artifacts_produced

    def _store_artifact(
        self, job_run: JobRun, file_version: FileVersion, artifact_result: ArtifactResult
    ) -> None:
        """Store artifact and create version with links.

        Args:
            job_run: JobRun tracking this pipeline execution
            file_version: Source FileVersion
            artifact_result: Generated artifact result
        """
        # Compute content hash
        content_json = json.dumps(artifact_result.content, sort_keys=True)
        content_hash = hashlib.sha256(content_json.encode()).hexdigest()

        # Create or get artifact
        artifact_key = f"{artifact_result.artifact_kind}:file:{file_version.version_id}"
        artifact = (
            self._db.query(Artifact).filter(Artifact.artifact_key == artifact_key).first()
        )

        if not artifact:
            artifact = Artifact(
                artifact_key=artifact_key,
                artifact_kind=artifact_result.artifact_kind,
                project_id=file_version.file.project_id,
            )
            self._db.add(artifact)
            self._db.flush()

        # Create artifact version
        # In production, content would be stored in a file
        content_locator = f"artifact_{artifact.artifact_id}_v{len(artifact.versions) + 1}.json"

        artifact_version = ArtifactVersion(
            artifact_id=artifact.artifact_id,
            job_run_id=job_run.job_id,
            content_locator=content_locator,
            content_hash=content_hash,
            metadata=artifact_result.metadata,
            is_current=True,
        )
        self._db.add(artifact_version)
        self._db.flush()

        # Mark previous versions as not current
        for old_version in artifact.versions:
            if old_version.version_id != artifact_version.version_id:
                old_version.is_current = False

        # Update artifact current version
        artifact.current_version_id = artifact_version.version_id

        # Create artifact link
        artifact_link = ArtifactLink(
            artifact_version_id=artifact_version.version_id,
            file_version_id=file_version.version_id,
            role_type=LinkRoleType.SOURCE,
            contribution_weight=1.0,
        )
        self._db.add(artifact_link)
        self._db.commit()

    def _normalize_content(self, content: str) -> str:
        """Normalize content by cleaning whitespace and line endings.

        Args:
            content: Raw content string

        Returns:
            Normalized content string
        """
        # Replace multiple spaces with single space
        normalized = re.sub(r" +", " ", content)

        # Replace multiple newlines with double newline (preserve paragraph breaks)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)

        # Normalize line endings to Unix style
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

        # Strip leading/trailing whitespace
        normalized = normalized.strip()

        return normalized

    def _read_file_content(self, file_version: FileVersion) -> str:
        """Read content from file version.

        In production, this would read from the content_locator path.
        For now, this is a placeholder that would be implemented based on
        storage strategy (filesystem, S3, database, etc.).

        Args:
            file_version: FileVersion to read

        Returns:
            File content as string

        Raises:
            RAGError: If file cannot be read
        """
        # This is a placeholder - in production, implement actual file reading
        # from content_locator based on storage strategy
        raise NotImplementedError(
            "File content reading not yet implemented - "
            "implement based on storage strategy (filesystem, S3, database)"
        )

    def _create_job_run(
        self,
        file_version_id: int,
        pipeline_name: str,
        backfill_job_id: Optional[int] = None,
    ) -> JobRun:
        """Create a new JobRun entity to track pipeline execution.

        Args:
            file_version_id: Source FileVersion ID
            pipeline_name: Name of the pipeline/rule
            backfill_job_id: Optional parent BackfillJob ID

        Returns:
            Created JobRun entity
        """
        job_run = JobRun(
            pipeline_name=pipeline_name,
            status=JobRunStatus.QUEUED,
            input_file_version_id=file_version_id,
            backfill_job_id=backfill_job_id,
            retry_count=0,
        )
        self._db.add(job_run)
        self._db.commit()

        return job_run

    def _create_job_step(self, job_run: JobRun, step_name: str) -> JobStep:
        """Create a new JobStep entity to track individual pipeline step.

        Args:
            job_run: Parent JobRun
            step_name: Step identifier (normalize, chunk, embed, generate_{kind})

        Returns:
            Created JobStep entity
        """
        job_step = JobStep(
            job_run_id=job_run.job_id,
            step_name=step_name,
            status=JobStepStatus.PENDING,
        )
        self._db.add(job_step)
        self._db.commit()

        return job_step

    def _update_job_metrics(self, job_run: JobRun, metrics: Dict[str, Any]) -> None:
        """Update JobRun metrics.

        Args:
            job_run: JobRun to update
            metrics: Metrics dictionary to update or merge
        """
        if job_run.metrics:
            job_run.metrics.update(metrics)
        else:
            job_run.metrics = metrics

        self._db.commit()
