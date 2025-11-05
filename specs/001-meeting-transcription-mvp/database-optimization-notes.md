# Database Optimization & Future Improvements

**Feature**: RAG-Enhanced Meeting Intelligence System
**Created**: 2025-11-05
**Status**: Post-Implementation Notes

## Overview

This document captures medium-term database optimization opportunities identified during the Phase 2 implementation review. These are not critical for MVP but should be considered as the system scales and matures.

---

## Medium-Term Optimizations (Post-MVP)

### 1. Automated Version Management with Database Triggers

**Context**: Currently, the application logic must ensure only one `is_current=true` version exists per File/Artifact.

**Recommendation**: Implement database triggers to automatically manage version flags.

**PostgreSQL Example**:
```sql
-- Trigger to ensure only one current version per file
CREATE OR REPLACE FUNCTION update_file_version_current()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_current = TRUE THEN
        -- Set all other versions for this file to is_current=FALSE
        UPDATE file_versions
        SET is_current = FALSE
        WHERE file_id = NEW.file_id
          AND version_id != NEW.version_id
          AND is_current = TRUE;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER file_version_current_trigger
    BEFORE INSERT OR UPDATE ON file_versions
    FOR EACH ROW
    EXECUTE FUNCTION update_file_version_current();
```

**Benefits**:
- Eliminates race conditions in application code
- Guarantees database-level consistency
- Simplifies application logic

**Migration Path**:
- SQLite (MVP): Application-level enforcement with transaction locks
- PostgreSQL (Production): Native trigger support
- Migration script: Add triggers during SQLite → PostgreSQL migration

---

### 2. Database Views for Common Query Patterns

**Context**: Several query patterns are repeated frequently across the codebase.

**Recommended Views**:

#### View 1: Current File Versions
```sql
CREATE VIEW current_file_versions AS
SELECT
    f.file_id,
    f.relative_path,
    f.mime_type,
    f.source_type,
    f.project_id,
    fv.version_id,
    fv.content_hash,
    fv.file_size_bytes,
    fv.content_locator,
    fv.discovered_at
FROM files f
JOIN file_versions fv ON f.current_version_id = fv.version_id
WHERE f.deleted = FALSE;
```

**Benefits**:
- Single join instead of two-step query
- Automatic filtering of deleted files
- Clearer intent in application queries

**Usage**:
```python
# Before:
file = session.query(File).filter_by(file_id=file_id).first()
version = session.query(FileVersion).filter_by(version_id=file.current_version_id).first()

# After:
current_version = session.query(CurrentFileVersion).filter_by(file_id=file_id).first()
```

#### View 2: Current Artifact Versions
```sql
CREATE VIEW current_artifact_versions AS
SELECT
    a.artifact_id,
    a.artifact_key,
    a.artifact_kind,
    a.project_id,
    av.version_id,
    av.content_locator,
    av.content_hash,
    av.metadata AS generation_metadata,
    av.created_at AS version_created_at,
    a.created_at AS artifact_created_at
FROM artifacts a
JOIN artifact_versions av ON a.current_version_id = av.version_id
WHERE a.deleted = FALSE;
```

#### View 3: Pending RAG Ingestion
```sql
CREATE VIEW pending_rag_ingestion AS
SELECT
    m.meeting_id,
    m.title,
    m.end_time,
    m.status AS meeting_status,
    m.rag_ingestion_status,
    t.transcript_id,
    t.word_count,
    t.speaker_count
FROM meetings m
JOIN transcripts t ON m.meeting_id = t.meeting_id
WHERE m.status = 'completed'
  AND (m.rag_ingestion_status IS NULL OR m.rag_ingestion_status = 'pending');
```

**Benefits**:
- MeetingRAGBridge service uses simpler query
- Centralized filtering logic
- Performance optimization via materialized views (PostgreSQL)

---

### 3. Table Partitioning for Scalability

**Context**: At scale (100k+ meetings, 1M+ chunks), certain tables will benefit from partitioning.

**Recommended Partitioning Strategy**:

#### Chunks Table - Partition by File Version
```sql
-- PostgreSQL 12+ declarative partitioning
CREATE TABLE chunks (
    chunk_id VARCHAR(255) PRIMARY KEY,
    file_version_id VARCHAR(255) NOT NULL,
    chunk_index INTEGER NOT NULL,
    text_content TEXT NOT NULL,
    -- ... other fields
) PARTITION BY HASH (file_version_id);

-- Create 8 partitions for load distribution
CREATE TABLE chunks_p0 PARTITION OF chunks FOR VALUES WITH (MODULUS 8, REMAINDER 0);
CREATE TABLE chunks_p1 PARTITION OF chunks FOR VALUES WITH (MODULUS 8, REMAINDER 1);
-- ... up to p7
```

**Benefits**:
- Query performance: Partition pruning limits scan scope
- Maintenance: VACUUM/ANALYZE runs faster on smaller partitions
- Archival: Drop old partitions for data retention

**When to Apply**:
- SQLite (MVP): No partitioning needed (<100k rows)
- PostgreSQL (Production): Apply when chunks table exceeds 500k rows

#### JobRun Table - Partition by Created Date
```sql
CREATE TABLE job_runs (
    job_run_id VARCHAR(255) PRIMARY KEY,
    -- ... other fields
    created_at TIMESTAMP NOT NULL
) PARTITION BY RANGE (created_at);

-- Monthly partitions for job history
CREATE TABLE job_runs_2025_11 PARTITION OF job_runs
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
CREATE TABLE job_runs_2025_12 PARTITION OF job_runs
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');
```

**Benefits**:
- Fast purging of old job history (DROP partition)
- Efficient archival (DETACH partition → export → cloud storage)
- Query performance for time-range filters

---

### 4. Materialized Views for Analytics

**Context**: Dashboard queries aggregate data across multiple tables.

**Recommended Materialized Views**:

#### MV 1: Job Success Metrics (Daily Aggregates)
```sql
CREATE MATERIALIZED VIEW job_metrics_daily AS
SELECT
    DATE(started_at) AS job_date,
    pipeline_name,
    status,
    COUNT(*) AS job_count,
    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) AS avg_duration_seconds,
    SUM((metrics->>'chunks_created')::int) AS total_chunks,
    SUM((metrics->>'llm_cost_estimate')::float) AS total_cost_usd
FROM job_runs
WHERE started_at IS NOT NULL
GROUP BY DATE(started_at), pipeline_name, status;

-- Refresh schedule: nightly cron job
CREATE INDEX idx_job_metrics_date ON job_metrics_daily(job_date DESC);
```

**Usage**:
```python
# Dashboard: "Show me last 30 days of ingestion stats"
metrics = session.query(JobMetricsDaily)\
    .filter(JobMetricsDaily.job_date >= date.today() - timedelta(days=30))\
    .all()
```

**Refresh Strategy**:
- Development: Manual refresh on demand
- Production: Scheduled refresh (daily at 2 AM via cron)

#### MV 2: Artifact Generation Statistics
```sql
CREATE MATERIALIZED VIEW artifact_stats_by_kind AS
SELECT
    a.artifact_kind,
    a.project_id,
    COUNT(DISTINCT a.artifact_id) AS total_artifacts,
    COUNT(av.version_id) AS total_versions,
    AVG((av.metadata->>'llm_cost_estimate')::float) AS avg_cost_per_artifact,
    MAX(av.created_at) AS last_generated_at
FROM artifacts a
JOIN artifact_versions av ON a.artifact_id = av.artifact_id
WHERE a.deleted = FALSE
GROUP BY a.artifact_kind, a.project_id;
```

---

### 5. Index Optimization for Production Workloads

**Context**: Initial indexes cover basic query patterns. Production usage may reveal additional optimization opportunities.

**Monitoring Strategy**:

1. **PostgreSQL Query Performance**:
   - Enable `pg_stat_statements` extension
   - Monitor slow queries (> 100ms)
   - Analyze `EXPLAIN ANALYZE` output

2. **Index Candidates**:
   - Composite indexes for multi-column filters
   - Partial indexes for common WHERE clauses
   - Covering indexes to avoid table lookups

**Example Partial Index**:
```sql
-- Index only active, non-deleted files for queries
CREATE INDEX idx_files_active ON files (project_id, source_type)
WHERE deleted = FALSE;
```

**Example Covering Index**:
```sql
-- Avoid lookups for file list queries
CREATE INDEX idx_files_list_covering ON files (project_id, created_at DESC)
INCLUDE (file_id, relative_path, mime_type, source_type);
```

---

### 6. Database Constraints Enhancement

**Context**: Some business rules are enforced at application level but could be database constraints.

**Recommended Additional Constraints**:

#### Unique Constraint: File Path per Project
```sql
-- Ensure unique relative_path within active files per project
CREATE UNIQUE INDEX idx_files_unique_path_per_project
ON files (project_id, relative_path)
WHERE deleted = FALSE;
```

**Benefit**: Prevents duplicate file ingestion at database level

#### Check Constraint: Artifact Version Metadata Validation
```sql
-- Ensure generation_metadata contains required keys (PostgreSQL)
ALTER TABLE artifact_versions
ADD CONSTRAINT check_metadata_required_keys
CHECK (
    metadata ? 'llm_provider' AND
    metadata ? 'llm_model' AND
    metadata ? 'schema_version'
);
```

**Benefit**: Data quality enforcement without application code

---

### 7. Full-Text Search Integration

**Context**: Users may want to search meeting transcripts and documents beyond vector similarity.

**Recommended Approach**:

#### PostgreSQL Full-Text Search
```sql
-- Add tsvector column to chunks for full-text search
ALTER TABLE chunks ADD COLUMN text_search_vector tsvector;

-- Populate with trigger
CREATE TRIGGER chunks_text_search_update
BEFORE INSERT OR UPDATE ON chunks
FOR EACH ROW EXECUTE FUNCTION
tsvector_update_trigger(text_search_vector, 'pg_catalog.english', text_content);

-- GIN index for fast full-text queries
CREATE INDEX idx_chunks_text_search ON chunks USING GIN(text_search_vector);
```

**Hybrid Search Query**:
```python
# Combine vector similarity + keyword matching
vector_results = chromadb.query(query_embedding, top_k=50)
keyword_results = session.query(Chunk).filter(
    Chunk.text_search_vector.match('deployment kubernetes')
).limit(50).all()

# Merge and re-rank results
combined_results = merge_and_rerank(vector_results, keyword_results)
```

---

### 8. Archival and Data Retention Strategy

**Context**: System accumulates historical data that may need archival.

**Recommended Policies**:

#### Hot/Cold Data Separation
- **Hot Data** (active queries): Last 90 days
- **Warm Data** (occasional access): 90 days - 1 year
- **Cold Data** (archival): > 1 year

**Implementation**:
```sql
-- Move old job_runs to archive table
CREATE TABLE job_runs_archive (LIKE job_runs INCLUDING ALL);

INSERT INTO job_runs_archive
SELECT * FROM job_runs
WHERE created_at < NOW() - INTERVAL '1 year';

DELETE FROM job_runs
WHERE created_at < NOW() - INTERVAL '1 year';
```

**Automated Retention**:
- Cron job: Monthly archival script
- Export to S3/GCS: Compressed JSONL files
- Compliance: GDPR/LGPD deletion requests trigger hard delete

---

## Performance Benchmarks (Target Metrics)

| Operation | Current (MVP) | Target (Post-Optimization) |
|-----------|---------------|----------------------------|
| Find pending RAG ingestion | ~50ms | <10ms (view) |
| Get current file version | ~30ms | <5ms (view) |
| Job list dashboard (100 jobs) | ~200ms | <50ms (indexes) |
| Full-text search (10k chunks) | N/A | <100ms (GIN index) |
| Artifact stats aggregation | ~500ms | <50ms (materialized view) |

---

## Migration Checklist (SQLite → PostgreSQL)

When transitioning from SQLite (dev) to PostgreSQL (production):

- [ ] Export SQLite data to SQL dump
- [ ] Create PostgreSQL schema with enhanced constraints
- [ ] Add triggers for version management
- [ ] Create views for common queries
- [ ] Create initial materialized views
- [ ] Set up partitioning for large tables
- [ ] Configure pg_stat_statements monitoring
- [ ] Tune PostgreSQL settings (shared_buffers, work_mem, etc.)
- [ ] Set up automated VACUUM/ANALYZE schedule
- [ ] Configure WAL archiving and point-in-time recovery
- [ ] Benchmark query performance and add missing indexes

---

## Summary

These optimizations represent the **next evolution** of the database design after MVP validation:

1. **Triggers**: Automate version management (eliminate application logic complexity)
2. **Views**: Simplify common queries (improve developer experience)
3. **Partitioning**: Scale to millions of rows (prepare for growth)
4. **Materialized Views**: Accelerate analytics (dashboard performance)
5. **Advanced Indexes**: Optimize production workloads (based on real usage patterns)
6. **Full-Text Search**: Hybrid retrieval (keyword + semantic search)
7. **Archival**: Data lifecycle management (compliance + cost optimization)

**Implementation Priority**:
- **Phase 1** (3 months post-MVP): Views, additional indexes
- **Phase 2** (6 months post-MVP): Materialized views, full-text search
- **Phase 3** (12 months post-MVP): Partitioning, archival automation

**Monitoring Strategy**:
- Track query performance with pg_stat_statements
- Set up alerting for slow queries (>100ms)
- Monthly review of index usage (unused indexes → candidates for removal)
- Quarterly review of table sizes and partition strategy
