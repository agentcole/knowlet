# Contributing

Thanks for contributing to Knowlet. This guide explains how to propose changes and what we expect in PRs.

## Ground Rules

- Be respectful and follow the Code of Conduct.
- Keep PRs focused and small when possible.
- Prefer clear, incremental changes over large refactors.

## Reporting Issues

Use the GitHub issue templates and include:

- Steps to reproduce
- Expected vs. actual behavior
- Logs or screenshots when relevant

## Development Setup

```bash
cp .env.example .env
docker compose up --build -d
```

## Tests and Checks

Backend:

```bash
docker compose exec -T backend python -m compileall app
```

Frontend:

```bash
docker compose exec -T frontend npm run build
```

## Pull Requests

- Use a clear title and concise description.
- Include test evidence (commands and results).
- Update documentation when behavior changes.

## License

By contributing, you agree that your contributions will be licensed under the project license.
