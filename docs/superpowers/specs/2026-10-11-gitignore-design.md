# HelpFlow `.gitignore` Design

## Goal

Add a root-level `.gitignore` tailored to the current Python project so local caches, environments, secrets, editor settings, logs, test output, and build artifacts are not committed.

## Rules

- Ignore Python bytecode and cache directories, including `__pycache__/` and `*.pyc`.
- Ignore local virtual environments such as `.venv/` and `venv/`.
- Ignore Python test, type-checker, linter, and coverage caches.
- Ignore packaging and build output.
- Ignore local environment files such as `.env`, while allowing example environment files to be committed.
- Ignore log files and operating-system metadata.
- Ignore the project-local `.vscode/` directory as requested.
- Keep source files, documentation, `pyproject.toml`, and `uv.lock` tracked.

## Verification

After creation, `git status --short` must no longer list Python cache files. The root `.gitignore`, project sources, documentation, `pyproject.toml`, and `uv.lock` must remain visible to Git.
