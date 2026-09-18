# Public Portfolio Phase 1 Tasks

## Goal

Prepare the repository for safe public publication by removing local database artifacts, preventing future local-state commits and Docker-context leaks, and documenting a reproducible pre-publication checklist in English.

## Scope

- Remove local SQLite artifacts from the repository working tree and Git index when tracked.
- Ignore local SQLite artifacts in Git and Docker contexts.
- Review repository-local Pi configuration and keep only project-safe configuration.
- Add an English public-release checklist covering secret scanning, Git-state review, attribution, and validation.

## Non-goals

- No GitHub remote changes, pushes, releases, or pull requests.
- No production deployment changes.
- No frontend UX redesign or demo-data implementation.
- No changes to real credentials or secrets.

## Tasks

- [x] Remove local database artifacts and verify they are no longer tracked.
- [x] Harden Git and Docker ignore rules for local database files and local harness state.
- [x] Write the English public-release checklist and verify repository hygiene.

## Evidence

- Removed local SQLite files `support-inbox/bff/support-inbox.db` and `support-inbox/bff/unused.db` from the Git index and working tree.
- Removed local `.pi/` and `.codegraph/` state from the Git index and working tree.
- Added local database patterns to `.gitignore` and `.dockerignore`; added `.pi/` to both local-state exclusions.
- Added `docs/public-release-checklist.md` in English.
- Verified `git diff --check` passes and `git ls-files` reports no database artifacts or local Pi/codegraph state.
- Recorded in the single feature work-unit commit `chore: harden public repository hygiene`, which also preserves the previously staged Support Inbox/BFF implementation and documentation.
