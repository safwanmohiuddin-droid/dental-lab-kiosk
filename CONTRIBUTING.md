# Contributing

Thanks for helping. The most useful contribution is feedback from people who run or work in a
dental lab: how materials are issued today, what is missing, what is confusing. Open an issue.

## Code
1. Open an issue first for anything bigger than a small fix.
2. Branch from `main`; one change per pull request.
3. Smallest change that fully solves the problem. No code "for later".
4. Every bug fix starts with a test that fails without the fix.
5. A choice that would be expensive to reverse gets an Architecture Decision Record in
   `docs/decisions/` (copy `0000-template.md`).
6. Commit messages: `[TAG] area: summary`, for example `[FIX] kiosk: ...`, `[ADD] reports: ...`.
7. Before pushing:

```bash
uv run ruff check . && uv run ruff format --check . && uv run python manage.py makemigrations --check && uv run pytest
```

CI runs the same checks plus a Docker build and smoke test. Development setup is in the README.

By contributing you agree that your contribution is licensed under AGPL-3.0.
