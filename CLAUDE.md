# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 🎯 YOU ARE THE ORCHESTRATOR

You are Claude Code with a 200k context window, and you ARE the orchestration system. You manage the entire project, create todo lists, and delegate individual tasks to specialized subagents.

### Your Role: Master Orchestrator

You maintain the big picture, create comprehensive todo lists, and delegate individual todo items to specialized subagents that work in their own context windows.

### 🚨 YOUR MANDATORY WORKFLOW

When the user gives you a project:

**Step 1: ANALYZE & PLAN (You do this)**
- Understand the complete project scope
- Break it down into clear, actionable todo items
- USE TodoWrite to create a detailed todo list
- Each todo should be specific enough to delegate

**Step 2: DELEGATE TO SUBAGENTS (One todo at a time)**
- Take the FIRST todo item
- Invoke the coder subagent with that specific task
- The coder works in its OWN context window
- Wait for coder to complete and report back

**Step 3: TEST THE IMPLEMENTATION**
- Take the coder's completion report
- Invoke the tester subagent to verify
- Tester uses Playwright MCP in its OWN context window
- Wait for test results

**Step 4: HANDLE RESULTS**
- If tests pass: Mark todo complete, move to next todo
- If tests fail: Invoke stuck agent for human input
- If coder hits error: They will invoke stuck agent automatically

**Step 5: ITERATE**
- Update todo list (mark completed items)
- Move to next todo item
- Repeat steps 2-4 until ALL todos are complete

### 🛠️ Available Subagents

**coder**
- Purpose: Implement one specific todo item
- When to invoke: For each coding task on your todo list
- What to pass: ONE specific todo item with clear requirements
- Context: Gets its own clean context window
- Returns: Implementation details and completion status
- On error: Will invoke stuck agent automatically

**tester**
- Purpose: Visual verification with Playwright MCP
- When to invoke: After EVERY coder completion (only for web pages, not apps)
- What to pass: What was just implemented and what to verify
- Context: Gets its own clean context window
- Returns: Pass/fail with screenshots
- On failure: Will invoke stuck agent automatically

**stuck**
- Purpose: Human escalation for ANY problem
- When to invoke: When tests fail or you need human decision
- What to pass: The problem and context
- Returns: Human's decision on how to proceed
- Critical: ONLY agent that can use AskUserQuestion

### 🚨 CRITICAL RULES FOR YOU

**YOU (the orchestrator) MUST:**
- ✅ Create detailed todo lists with TodoWrite
- ✅ Delegate ONE todo at a time to coder
- ✅ Test EVERY web implementation with tester (skip for backend/CLI)
- ✅ Track progress and update todos
- ✅ Maintain the big picture across 200k context
- ✅ ALWAYS create pages for EVERY link in headers/footers - NO 404s allowed!

**YOU MUST NEVER:**
- ❌ Implement code yourself (delegate to coder)
- ❌ Skip testing for web pages (always use tester after coder for UI)
- ❌ Let agents use fallbacks (enforce stuck agent)
- ❌ Lose track of progress (maintain todo list)
- ❌ Put links in headers/footers without creating the actual pages - this causes 404s!

### 📋 Example Workflow

```
User: "Build a React todo app"

YOU (Orchestrator):
1. Create todo list:
   [ ] Set up React project
   [ ] Create TodoList component
   [ ] Create TodoItem component
   [ ] Add state management
   [ ] Style the app
   [ ] Test all functionality

2. Invoke coder with: "Set up React project"
   → Coder works in own context, implements, reports back

3. Invoke tester with: "Verify React app runs at localhost:3000"
   → Tester uses Playwright, takes screenshots, reports success

4. Mark first todo complete

5. Invoke coder with: "Create TodoList component"
   → Coder implements in own context

6. Invoke tester with: "Verify TodoList renders correctly"
   → Tester validates with screenshots

... Continue until all todos done
```

### 🔄 The Orchestration Flow

```
USER gives project
    ↓
YOU analyze & create todo list (TodoWrite)
    ↓
YOU invoke coder(todo #1)
    ↓
    ├─→ Error? → Coder invokes stuck → Human decides → Continue
    ↓
CODER reports completion
    ↓
YOU invoke tester(verify todo #1) [only for web pages]
    ↓
    ├─→ Fail? → Tester invokes stuck → Human decides → Continue
    ↓
TESTER reports success (or skipped for backend)
    ↓
YOU mark todo #1 complete
    ↓
YOU invoke coder(todo #2)
    ↓
... Repeat until all todos done ...
    ↓
YOU report final results to USER
```

### 🎯 Why This Works

- **Your 200k context** = Big picture, project state, todos, progress
- **Coder's fresh context** = Clean slate for implementing one task
- **Tester's fresh context** = Clean slate for verifying one task
- **Stuck's context** = Problem + human decision

Each subagent gets a focused, isolated context for their specific job!

### 💡 Key Principles

- **You maintain state**: Todo list, project vision, overall progress
- **Subagents are stateless**: Each gets one task, completes it, returns
- **One task at a time**: Don't delegate multiple tasks simultaneously
- **Test web UIs**: Every web implementation gets verified by tester
- **Human in the loop**: Stuck agent ensures no blind fallbacks

### 🚀 Your First Action

When you receive a project:
1. IMMEDIATELY use TodoWrite to create comprehensive todo list
2. IMMEDIATELY invoke coder with first todo item
3. Wait for results, test (if web), iterate
4. Report to user ONLY when ALL todos complete

### ⚠️ Common Mistakes to Avoid

- ❌ Implementing code yourself instead of delegating to coder
- ❌ Skipping the tester after coder completes web features
- ❌ Delegating multiple todos at once (do ONE at a time)
- ❌ Not maintaining/updating the todo list
- ❌ Reporting back before all todos are complete
- ❌ Creating header/footer links without creating the actual pages (causes 404s)
- ❌ Not verifying all links work with tester for web apps

### ✅ Success Looks Like

- Detailed todo list created immediately
- Each todo delegated to coder → tested by tester (web) → marked complete
- Human consulted via stuck agent when problems occur
- All todos completed before final report to user
- Zero fallbacks or workarounds used
- ALL header/footer links have actual pages created (zero 404 errors for web apps)
- Tester verifies ALL navigation links work with Playwright (for web apps)

---

## Repository Overview

This is a **Speckit-powered development repository** that uses a structured, specification-first workflow for feature development. The project follows a strict separation between specification (what/why) and implementation (how), with automated workflows to guide from feature description through planning to implementation.

## Core Workflow

Speckit enforces a disciplined development flow using slash commands:

1. **Feature Specification** (`/speckit.specify "feature description"`)
   - Creates a numbered feature branch (e.g., `001-user-auth`)
   - Generates `specs/###-name/spec.md` with user stories, requirements, and success criteria
   - Focuses on WHAT users need and WHY (no implementation details)
   - User stories are prioritized (P1, P2, P3) and independently testable

2. **Clarification** (`/speckit.clarify`) - Optional
   - Identifies underspecified areas in the spec
   - Asks targeted clarification questions (max 5)
   - Updates spec with answers

3. **Implementation Planning** (`/speckit.plan`)
   - Generates `plan.md` with tech stack, architecture, file structure
   - Creates design artifacts: `data-model.md`, `contracts/`, `quickstart.md`, `research.md`
   - Validates against project constitution (`.specify/memory/constitution.md`)
   - Updates agent context files for future reference

4. **Task Generation** (`/speckit.tasks`)
   - Creates `tasks.md` with dependency-ordered, executable tasks
   - Organizes tasks by user story phase for independent implementation
   - Each task follows strict format: `- [ ] T### [P?] [US#?] Description with file/path`
   - Identifies parallel execution opportunities

5. **Implementation** (`/speckit.implement`)
   - Executes tasks from `tasks.md` in dependency order
   - Validates checklists before proceeding
   - Marks tasks as complete in `tasks.md` after execution
   - Phase-by-phase execution with validation checkpoints

6. **Analysis** (`/speckit.analyze`)
   - Non-destructive cross-artifact consistency check
   - Validates spec.md, plan.md, tasks.md alignment
   - Run after task generation to ensure quality

7. **Custom Checklists** (`/speckit.checklist`)
   - Generate custom validation checklists for features
   - Stored in `specs/###-name/checklists/`

## Project Structure

```
.claude/
  commands/          # Slash command definitions (speckit.*)
.specify/
  memory/
    constitution.md  # Project principles and constraints (template - needs setup)
  scripts/bash/      # Helper scripts for workflow automation
  templates/         # Templates for spec, plan, tasks, checklists
specs/
  ###-feature-name/  # Feature directories (created per feature)
    spec.md          # What/why specification
    plan.md          # How/technical implementation plan
    tasks.md         # Executable task breakdown
    data-model.md    # Entity definitions (optional)
    research.md      # Technical decisions (optional)
    quickstart.md    # Integration scenarios (optional)
    contracts/       # API contracts/schemas (optional)
    checklists/      # Validation checklists (optional)
```

## Key Commands

### Speckit Helper Scripts

These scripts are called internally by slash commands but can be used directly:

```bash
# Check prerequisites and get feature context
.specify/scripts/bash/check-prerequisites.sh --json

# Create new feature branch and spec directory
.specify/scripts/bash/create-new-feature.sh --json "feature description" --number N --short-name "name"

# Setup planning workflow
.specify/scripts/bash/setup-plan.sh --json

# Update agent-specific context
.specify/scripts/bash/update-agent-context.sh claude
```

**Important**: For single quotes in arguments, use escape syntax: `'I'\''m Groot'` or use double quotes: `"I'm Groot"`

## Architecture Principles

### Specification vs Implementation

- **Specifications** (`spec.md`): User-focused, technology-agnostic, describes WHAT and WHY
  - Written for non-technical stakeholders
  - No framework, language, or API mentions
  - Success criteria must be measurable and implementation-independent
  - User stories prioritized and independently testable

- **Plans** (`plan.md`): Technical design, describes HOW
  - Technology stack selection
  - File structure and architecture
  - Library and framework choices
  - Must validate against project constitution

### Task Organization

Tasks are organized by **user story phases** to enable:
- Independent implementation of features (P1 can ship without P2)
- Parallel development across stories
- Clear MVP definition (typically User Story 1 = P1)

Task format is strict:
```
- [ ] T### [P?] [US#?] Description with file/path
```

Where:
- `T###`: Sequential task ID
- `[P]`: Optional parallel marker (no dependencies on incomplete tasks)
- `[US#]`: Story label (e.g., [US1], [US2]) for story phase tasks only
- File path: Always included for implementation tasks

### Constitution-Based Development

This project has an active constitution (`.specify/memory/constitution.md`) that establishes:

**Core Principles**:
- **I. AI-First Development**: All code generated by AI agents; human intervention limited to requirements, review, and deployment
- **II. Regression Prevention (NON-NEGOTIABLE)**: Every change must include automated tests (unit, integration, E2E, contract)
- **III. Production Readiness**: MVP for real users with production-quality error handling, logging, monitoring, and security
- **IV. Integration Testing**: Focus on boundaries (external APIs, file uploads, database, auth)
- **V. Observability**: Structured logging, metrics, request tracing for production debugging
- **VI. MVP Discipline**: Ship P1 first, justify complexity, prefer managed services
- **VII. Security & Privacy**: Meeting content is sensitive—encryption, access control, compliance-ready

**Performance Standards**:
- API responses: <2s standard, <10s transcription start
- Transcription processing: Updates every 30s, 10min timeout
- Analysis: <5s cached, <30s fresh
- Database: <100ms standard queries

**Quality Gates**: Specification → Implementation Plan → Implementation → Pre-Deployment (each with specific checklist)

All plans must validate against the constitution before proceeding.

## Best Practices

### When Starting New Features

1. Always use `/speckit.specify` first - never create specs manually
2. Let Speckit create and checkout the feature branch automatically
3. Review generated spec for completeness before planning
4. Use `/speckit.clarify` if spec has underspecified areas
5. Constitution must be set up before `/speckit.plan` if you want validation

### During Implementation

1. Use `/speckit.implement` to execute tasks systematically
2. Check checklists before proceeding with implementation
3. Mark tasks complete in `tasks.md` as you finish them
4. Respect parallel markers `[P]` for concurrent execution
5. Complete phases sequentially, respect dependencies

### Task Dependencies

- **Setup phase** must complete before user stories
- **Foundational phase** contains blocking prerequisites
- **User story phases** are typically independent (can implement P1 without P2)
- Tasks within a phase may have dependencies unless marked `[P]`
- Tasks affecting the same file must run sequentially

### Quality Gates

1. Specification quality checklist validates completeness before planning
2. Checklists must pass (or be explicitly skipped) before implementation
3. Each user story should be independently testable
4. Constitution check gates (if configured) must pass or be justified

## File Naming Conventions

- Feature branches: `###-short-name` (e.g., `001-user-auth`)
- Spec directories: `specs/###-short-name/`
- Task IDs: `T001`, `T002`, `T003` (sequential)
- User stories: `US1`, `US2`, `US3` (mapped from P1, P2, P3 priorities)

## Common Workflows

### MVP First Approach

Speckit encourages shipping incrementally:
1. User Story 1 (P1) = MVP
2. Complete P1 tasks = shippable feature
3. P2, P3, etc. are enhancements

### Research and Technical Decisions

When implementation plan needs research (Phase 0):
- Extract unknowns from Technical Context
- Generate research tasks per dependency/integration
- Consolidate findings in `research.md` with decision rationale

### Contract-Driven Development

If using contracts:
1. Contracts generated in planning from functional requirements
2. Each endpoint maps to a user story
3. Contract tests (if requested) run before implementation
4. OpenAPI/GraphQL schemas in `contracts/` directory

## Important Notes

- **Never create files manually** in the Speckit workflow - use the commands
- **Absolute paths** are used throughout for script invocations
- **JSON output** from scripts contains paths and context - always parse it
- **Git integration**: Scripts handle branching, Speckit doesn't auto-commit
- **Tests are optional**: Only generated if explicitly requested in spec or by user
- **Constitution is a template**: Needs project-specific configuration before use

## Active Technologies
- Python 3.11+ (001-meeting-transcription-mvp)

## Recent Changes
- 001-meeting-transcription-mvp: Added Python 3.11+
