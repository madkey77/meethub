<!--
Sync Impact Report:
- Version change: [TEMPLATE] → 1.0.0 (initial ratification)
- Modified principles: N/A (initial version)
- Added sections:
  * Core Principles (I-VII): AI-First Development, Regression Prevention, Production Readiness,
    Integration Testing, Observability, MVP Discipline, Security & Privacy
  * MVP-Specific Constraints
  * Quality Gates
- Removed sections: N/A
- Templates requiring updates:
  ✅ .specify/templates/plan-template.md (validated - Constitution Check section compatible)
  ✅ .specify/templates/spec-template.md (validated - success criteria alignment)
  ✅ .specify/templates/tasks-template.md (validated - test task phases compatible)
  ✅ .claude/commands/*.md (validated - no agent-specific conflicts)
- Follow-up TODOs: None
-->

# MeetHub Constitution

## Core Principles

### I. AI-First Development

All code in this project MUST be generated and maintained by AI agents (primarily Claude Code).
Human intervention is limited to:
- Requirements specification and clarification
- Code review and approval
- Testing validation
- Production deployment decisions

**Rationale**: This project serves as an AI-capability demonstration. Maintaining AI-only
code generation ensures consistency, reproducibility, and showcases the viability of
fully AI-driven development for production systems.

**Rules**:
- No manual code edits without documenting rationale in commit messages
- All features developed via Speckit workflow (`/speckit.specify` → `/speckit.plan` →
  `/speckit.tasks` → `/speckit.implement`)
- AI agents MUST follow established architecture and patterns from prior generations

### II. Regression Prevention (NON-NEGOTIABLE)

Every feature change MUST include automated tests that prevent future breakage.

**Test Requirements**:
- **Unit tests**: For all business logic, data transformations, and utilities
- **Integration tests**: For API endpoints, database interactions, external service calls
- **E2E tests**: For critical user workflows (meeting upload → transcription → analysis)
- **Contract tests**: For all API contracts and data model changes

**Testing Discipline**:
- Tests MUST be written during implementation (not after)
- New features require tests before marking tasks complete
- Bug fixes require regression tests that would have caught the bug
- Test coverage MUST NOT decrease with new changes
- All tests MUST pass before considering feature complete

**Rationale**: As an AI-coded MVP for user testing, stability is critical. Users will not
adopt a system that breaks frequently. Comprehensive automated testing is the only way to
ensure changes don't break existing functionality when AI agents make modifications.

### III. Production Readiness

This is an MVP intended for REAL USERS, not a prototype. Every feature MUST meet
production quality standards.

**Production Requirements**:
- Error handling: Graceful degradation, user-friendly error messages, no exposed stack traces
- Logging: Structured logging for all critical operations (transcription jobs, analysis
  requests, failures)
- Monitoring: Health checks, metrics endpoints, performance tracking
- Data integrity: Validation at API boundaries, database constraints, transaction safety
- Security: Input sanitization, authentication/authorization, secure credential storage

**Performance Standards**:
- API response times: <2s for standard requests, <10s for transcription initiation
- Transcription processing: Status updates every 30s, timeout handling after 10min
- Analysis generation: <5s for cached results, <30s for new analysis
- Database queries: Indexed appropriately, <100ms for standard lookups

**Rationale**: Users will evaluate this system's viability for their workflows. Poor
performance, crashes, or data loss will immediately disqualify it from consideration.

### IV. Integration Testing

Focus integration testing on boundaries where failures commonly occur:

**Critical Integration Points**:
- Transcription service API calls (external dependency, rate limits, timeouts)
- Audio file uploads and storage (file size limits, format validation, storage failures)
- Database transactions (concurrent access, data consistency)
- Analysis pipeline (multi-step processing, intermediate failures)
- Authentication/authorization (session management, token validation)

**Integration Test Strategy**:
- Use test doubles (mocks/stubs) for external services in standard tests
- Maintain separate integration test suite that uses real dependencies (test environment)
- Run integration tests in CI/CD pipeline before deployment
- Document expected failure modes and recovery procedures

### V. Observability

System MUST be debuggable in production without direct access.

**Logging Requirements**:
- Structured JSON logs with standard fields (timestamp, level, service, request_id, user_id)
- Log all state transitions (meeting created, transcription started, transcription completed,
  analysis generated)
- Log all errors with context (user action, input parameters, error details)
- No sensitive data in logs (audio content, personal identifiers beyond IDs)

**Metrics Requirements**:
- Request counts and response times per endpoint
- Transcription job durations and success/failure rates
- Analysis generation times and cache hit rates
- Error rates by type and endpoint

**Tracing**:
- Request correlation IDs through entire workflow
- Track user journey: upload → transcription → analysis → export

### VI. MVP Discipline

Start with the simplest solution that delivers user value. Complexity MUST be justified.

**MVP Principles**:
- Ship User Story 1 (P1) as the minimum viable product
- Additional features (P2, P3+) are enhancements, not blockers
- Prefer proven libraries over custom implementations
- Use managed services over self-hosted when possible (transcription APIs, storage, databases)
- Defer optimization until proven necessary by user feedback or metrics

**Scope Control**:
- Each feature must justify its inclusion for the MVP
- "Nice to have" features deferred to post-MVP backlog
- User feedback determines priority for P2+ features

**Rationale**: Limited testing users means we need to iterate quickly based on real usage
patterns, not assumptions. Overengineering delays learning.

### VII. Security & Privacy

Meeting content is sensitive. Security and privacy are non-negotiable.

**Security Requirements**:
- Authentication required for all endpoints (except health checks)
- Authorization: Users can only access their own meetings/transcriptions
- Audio files: Encrypted at rest, secure upload/download signed URLs
- Transcriptions: Access-controlled, no public sharing without explicit user action
- API keys/credentials: Environment variables only, never committed to repository
- Input validation: All user inputs sanitized, file uploads validated (type, size)

**Privacy Requirements**:
- Minimal data collection: Only what's necessary for functionality
- Data retention: Clear policy for when transcriptions/audio are deleted
- Third-party services: Document what data is sent to transcription APIs
- User consent: Clear terms for how meeting content is processed and stored

**Compliance Considerations**:
- Prepare for GDPR/CCPA if users request data deletion
- No audio content analysis beyond user-initiated actions
- Audit logging for sensitive operations (data access, deletion)

## MVP-Specific Constraints

**Technology Stack**:
- Prefer mainstream, well-documented technologies with strong AI agent support
- Prioritize technologies that AI agents (Claude Code) can confidently implement
- Use language/framework where comprehensive test libraries exist

**Deployment**:
- Must be deployable to a single cloud provider account (AWS, GCP, or Azure)
- Infrastructure as Code (IaC) for reproducibility
- Environment separation: development, staging (for user testing), production (future)
- Rollback capability: Every deployment must be revertable

**Documentation**:
- README.md: Setup instructions, architecture overview, testing instructions
- API documentation: Auto-generated from code (OpenAPI/Swagger)
- Deployment guide: Step-by-step production deployment process
- Troubleshooting guide: Common issues and resolution steps

## Quality Gates

Every feature MUST pass these gates before considered complete:

**Gate 1: Specification**
- [ ] User stories are clear and testable
- [ ] Success criteria are measurable
- [ ] Edge cases identified
- [ ] Security implications assessed

**Gate 2: Implementation Plan**
- [ ] Architecture follows established patterns
- [ ] Dependencies identified and justified
- [ ] Test strategy defined
- [ ] Rollback plan documented

**Gate 3: Implementation**
- [ ] All tasks in tasks.md completed
- [ ] Tests written and passing (unit, integration, E2E where applicable)
- [ ] Code follows established patterns
- [ ] No hardcoded credentials or sensitive data
- [ ] Error handling implemented
- [ ] Logging added for critical operations

**Gate 4: Pre-Deployment**
- [ ] All tests pass in CI/CD pipeline
- [ ] Integration tests pass against test environment
- [ ] Performance benchmarks meet standards
- [ ] Security scan passes (dependency vulnerabilities, secret detection)
- [ ] Documentation updated

## Governance

**Amendment Process**:
- Constitution changes require explicit rationale in commit message
- Version increments follow semantic versioning (MAJOR.MINOR.PATCH)
- All amendments update this document's version footer and Sync Impact Report

**Compliance Verification**:
- All planning phases (`/speckit.plan`) MUST validate against this constitution
- Code reviews MUST verify adherence to principles
- Failed gates require fixes before proceeding to next phase

**Conflict Resolution**:
- If a principle conflicts with practical delivery, document the trade-off and get
  explicit approval before proceeding
- Technical debt is acceptable if documented and scheduled for resolution

**Living Document**:
- This constitution evolves based on learnings from user testing
- User feedback may trigger principle amendments
- Agent capabilities improvements may enable stricter standards

For detailed implementation guidance during development, see CLAUDE.md.

**Version**: 1.0.0 | **Ratified**: 2025-10-31 | **Last Amended**: 2025-10-31
