# Contributing Guidelines

## Local development

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
2. Install project dependencies with `uv sync`.
3. Run the integration locally with `./scripts/run`, then open
   <http://localhost:8123>.
4. Configure the integration through the Home Assistant UI.

## Testing

Run the complete local check suite before opening a pull request:

```bash
uv run ruff check && uv run ruff format --check && uv run ty check && uv run pytest
```

Run the test suite:

```bash
uv run pytest
```

Run one test module without the coverage threshold:

```bash
uv run pytest --cov-fail-under=0 tests/test_init.py
```

## Contributing

Contributions are welcome! Please follow these steps:

1. **Fork the repository** on GitHub
2. **Create a feature or fix branch** from `main` for your work:
   ```bash
   git checkout -b feature/my-feature
   # or for a bug fix:
   git checkout -b fix/my-bugfix
   ```
3. **Make your changes** in your created branch and test them locally.
   Keep user-facing behavior and translations in sync, and add or update tests
   when changing integration behavior.
4. **Commit your changes** with clear commit messages:
   ```bash
   git commit -m "feat: add new feature"
   # or
   git commit -m "fix: resolve issue #123"
   ```
5. **Push your branch** to your fork:
   ```bash
   git push origin feature/my-feature
   # or
   git push origin fix/my-bugfix
   ```
6. **Open a Pull Request** against the `main` branch of the original repository
   - Describe your changes in the PR description
   - Reference any related issues
   - Ensure the complete local check suite passes before submitting

The repository owner will review your PR and merge it if appropriate.

## License

By contributing, you agree that your contributions will be licensed under its GNU AFFERO GENERAL PUBLIC LICENSE Version 3 License.

## Funding

If you find this project useful, consider supporting its development:

<a href="https://www.buymeacoffee.com/hunter.nl" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;"></a>
