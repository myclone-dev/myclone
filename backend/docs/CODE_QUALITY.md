# Code Quality and Formatting Guide

This document describes the code quality tools, linting, formatting, and pre-commit hooks setup for the Expert Clone project.

---

## 🛠️ Tools Overview

We use a comprehensive set of tools to maintain code quality:

| Tool | Purpose | Auto-fix |
|------|---------|----------|
| **Black** | Python code formatter (opinionated) | ✅ Yes |
| **isort** | Import statement organizer | ✅ Yes |
| **Ruff** | Fast Python linter (replaces flake8, pylint) | ✅ Partial |
| **mypy** | Static type checker | ❌ No |
| **Bandit** | Security vulnerability scanner | ❌ No |
| **pre-commit** | Git hook framework | ✅ Orchestrates all tools |

---

## 📦 Installation

### 1. Install Dependencies

```bash
# Install all dev dependencies (including linting tools)
poetry install --with dev

# Or update if already installed
poetry update
```

### 2. Install Pre-commit Hooks

```bash
# Install git hooks
poetry run pre-commit install

# Verify installation
poetry run pre-commit --version
```

---

## 🚀 Usage

### Automatic (Recommended)

Once pre-commit hooks are installed, they run automatically on every `git commit`:

```bash
git add .
git commit -m "Your commit message"
# Pre-commit hooks run automatically and may modify files
# If files are modified, you'll need to re-add them and commit again
```

### Manual Execution

Run checks manually without committing:

```bash
# Run on all files
poetry run pre-commit run --all-files

# Run on specific files
poetry run pre-commit run --files app/config.py app/main.py

# Run on staged files only
poetry run pre-commit run
```

### Individual Tools

Run tools separately for debugging or CI/CD:

```bash
# Format code with Black
poetry run black .
poetry run black app/  # specific directory
poetry run black --check .  # check only, don't modify

# Sort imports with isort
poetry run isort .
poetry run isort --check-only .  # check only

# Lint with Ruff
poetry run ruff check .
poetry run ruff check --fix .  # auto-fix issues
poetry run ruff format .  # format (similar to black)

# Type check with mypy
poetry run mypy app/ workers/ livekit/ shared/
poetry run mypy --ignore-missing-imports app/

# Security scan with Bandit
poetry run bandit -r app/ workers/ livekit/ shared/
poetry run bandit -r app/ -c pyproject.toml  # with config
```

---

## ⚙️ Configuration

All tool configurations are in `pyproject.toml`:

### Black Configuration
```toml
[tool.black]
line-length = 100
target-version = ['py311']
```

### isort Configuration
```toml
[tool.isort]
profile = "black"  # Compatible with Black
line_length = 100
```

### Ruff Configuration
```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "C", "B", "UP"]
ignore = ["E501"]  # Line too long (handled by black)
```

### mypy Configuration
```toml
[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true
check_untyped_defs = true
```

### Bandit Configuration
```toml
[tool.bandit]
exclude_dirs = ["tests", "alembic/versions", ".venv"]
skips = ["B101", "B601"]
```

---

## 🔧 Pre-commit Hooks

Configured in `.pre-commit-config.yaml`. The following hooks run on every commit:

1. **General File Checks**
   - Trailing whitespace removal
   - End-of-file fixer
   - YAML/JSON validation
   - Large file detection
   - Merge conflict detection
   - Private key detection

2. **Python Code Quality**
   - isort (import sorting)
   - Black (code formatting)
   - Ruff (linting + formatting)
   - mypy (type checking)
   - Bandit (security checks)
   - Safety (dependency vulnerability checks)

### Excluded Paths

The following paths are excluded from checks:
- `alembic/versions/` - Auto-generated migration files
- `.venv/` - Virtual environment
- `build/`, `dist/` - Build artifacts

---

## 🤖 GitHub Actions CI/CD

Automated checks run on every push to `main` and `staging` branches.

**Workflow**: `.github/workflows/code-quality.yml`

### Jobs

1. **lint-and-format**
   - Runs Black, isort, Ruff, mypy, Bandit
   - Fails if formatting or linting issues found
   - Matrix strategy for multiple Python versions

2. **pre-commit-check**
   - Runs all pre-commit hooks
   - Uses caching for faster runs
   - Fails if any hook fails

3. **code-quality-summary**
   - Aggregates results from all jobs
   - Reports overall status

### Viewing Results

- Go to **Actions** tab in GitHub repository
- Click on the workflow run
- View detailed logs for each job
- Failed checks will block PR merging (if configured)

---

## 📝 Common Workflows

### Before Committing

```bash
# 1. Format all code
poetry run black .
poetry run isort .

# 2. Check for linting issues
poetry run ruff check --fix .

# 3. Run all pre-commit checks
poetry run pre-commit run --all-files

# 4. Commit if all checks pass
git add .
git commit -m "Your message"
```

### Fixing Specific Issues

#### Import Order Issues
```bash
poetry run isort app/
```

#### Code Formatting Issues
```bash
poetry run black app/
```

#### Linting Errors
```bash
# Auto-fix what's possible
poetry run ruff check --fix .

# Review remaining issues
poetry run ruff check .
```

#### Type Checking Issues
```bash
# Run mypy on specific module
poetry run mypy app/core/llama_rag.py

# Ignore missing imports for external libraries
poetry run mypy --ignore-missing-imports app/
```

### Skipping Hooks (Not Recommended)

```bash
# Skip all pre-commit hooks (emergency only!)
git commit --no-verify -m "Emergency fix"

# Skip specific hook
SKIP=mypy git commit -m "Skip mypy for now"
```

---

## 🧪 Testing Your Changes

After modifying `.pre-commit-config.yaml` or `pyproject.toml`:

```bash
# Update pre-commit hooks
poetry run pre-commit clean
poetry run pre-commit install

# Test on a single file
poetry run pre-commit run --files app/config.py

# Test on all files
poetry run pre-commit run --all-files
```

---

## 🐛 Troubleshooting

### Pre-commit hooks not running

```bash
# Reinstall hooks
poetry run pre-commit uninstall
poetry run pre-commit install

# Verify installation
ls -la .git/hooks/pre-commit
```

### Pre-commit hooks taking too long

```bash
# Clear cache and reinstall
poetry run pre-commit clean
poetry run pre-commit gc

# Run specific hooks only
SKIP=mypy,bandit git commit -m "Message"
```

### Poetry installation issues

```bash
# Update Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Clear cache
poetry cache clear pypi --all
poetry cache clear . --all

# Reinstall dependencies
rm poetry.lock
poetry install --with dev
```

### Black and isort conflicts

Both tools are configured to work together (`isort profile = "black"`). If you see conflicts:

```bash
# Run isort first, then black
poetry run isort .
poetry run black .
```

---

## 📚 Additional Resources

- [Black Documentation](https://black.readthedocs.io/)
- [isort Documentation](https://pycqa.github.io/isort/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [mypy Documentation](https://mypy.readthedocs.io/)
- [Bandit Documentation](https://bandit.readthedocs.io/)
- [pre-commit Documentation](https://pre-commit.com/)

---

## ✅ Best Practices

1. **Run pre-commit before pushing**: `poetry run pre-commit run --all-files`
2. **Fix issues incrementally**: Don't let formatting debt accumulate
3. **Use auto-fix features**: Let tools fix what they can automatically
4. **Commit formatted code**: Never commit with `--no-verify` unless emergency
5. **Keep configs updated**: Review tool versions in `.pre-commit-config.yaml` quarterly
6. **Monitor CI/CD**: Check GitHub Actions for any failures
7. **Document exceptions**: If you must skip a check, document why in comments

---

## 🔄 Maintenance

### Updating Pre-commit Hooks

```bash
# Update to latest versions
poetry run pre-commit autoupdate

# Review changes
git diff .pre-commit-config.yaml

# Test updated hooks
poetry run pre-commit run --all-files
```

### Updating Python Dependencies

```bash
# Update dev dependencies
poetry update --with dev

# Regenerate lock file
poetry lock

# Install updated deps
poetry install --with dev
```

---

## 📋 Checklist for New Developers

- [ ] Install Poetry: `curl -sSL https://install.python-poetry.org | python3 -`
- [ ] Install dependencies: `poetry install --with dev`
- [ ] Install pre-commit: `poetry run pre-commit install`
- [ ] Test setup: `poetry run pre-commit run --files app/config.py`
- [ ] Read this guide: `docs/CODE_QUALITY.md`
- [ ] Configure IDE: Set Black as formatter, line length = 100
- [ ] Make a test commit to verify hooks work

---

**Questions?** Check [CLAUDE.md](../CLAUDE.md) or ask the team!
