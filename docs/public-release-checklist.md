# Public Release Checklist

Use this checklist before pushing this repository to a public GitHub remote. Production secrets must never be committed.

- Review the worktree and index: `git status --short` and `git diff --cached --name-only`.
- Confirm no local database artifacts are tracked: `git ls-files '*.db' '*.sqlite' '*.sqlite3'`.
- Scan tracked text files for likely credentials without printing their contents: `git grep -IlE '(BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY|api[_-]?key|secret[_-]?key|password)'`.
- Verify that a local environment file is ignored and untracked: `git check-ignore -q .env && ! git ls-files --error-unmatch .env >/dev/null`.
- When frontend output is intentionally committed, inspect its change before staging it: `git diff --stat -- frontend/` and `git diff --check -- frontend/`.
- Preserve required upstream attribution and license notices; review `LICENSE` and copied-source headers before publishing.
- Run focused validation for the changed area (for example, `./scripts/validate.sh` for Python changes) and resolve failures before pushing.
- Confirm the README accurately states the public project identity and repository URLs.
