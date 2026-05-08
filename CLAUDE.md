# Patchbay Plugin — Claude Routing

Project-specific instructions for AI assistants working in this repository.

## Project context

Patchbay is a Claude Code plugin for musicians — a project-agnostic toolkit that helps users use the gear they already own. The eventual UX is a conversational AI that answers gear questions and lets the user hover any sentence in the answer to jump to the source (manual page, video timestamp, review paragraph). See [README.md](README.md) for the high-level pitch and [.planning/notes/knowledge-architecture.md](.planning/notes/knowledge-architecture.md) for the architectural foundation.

## Auto-load routing

- **Spike findings for patchbay-plugin** (implementation patterns, constraints, gotchas, validated chunk schema, source-class blueprints) → `Skill("spike-findings-patchbay-plugin")`
