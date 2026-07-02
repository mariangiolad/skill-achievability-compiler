# Contributing to skill-achievability-compiler

Thank you for your interest in contributing to the skill-achievability-compiler! This document provides guidelines and instructions for contributing.

## Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please be respectful in all interactions.

## How to Contribute

### Reporting Bugs

If you find a bug, please open a GitHub issue with:
- A clear, descriptive title
- A description of the bug and its impact
- Steps to reproduce the issue
- Expected vs. actual behavior
- Your environment (Python version, OS, etc.)

### Suggesting Enhancements

Enhancement suggestions are also welcome via GitHub issues. Please include:
- A clear, descriptive title
- A detailed description of the proposed enhancement
- Rationale for why this would be useful
- Examples of how it would work

### Pull Requests

1. **Fork the repository** and create a feature branch from `gc/implement-and-testing`.
2. **Make your changes** following the coding style of the project.
3. **Write or update tests** to cover your changes (see `tests/`).
4. **Run the test suite** to ensure all tests pass:
   ```bash
   python3 -m pytest
   ```
5. **Update documentation** as needed (README, docstrings, etc.).
6. **Submit a pull request** with a clear description of your changes.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/ginaecho/skill-achievability-compiler.git
cd skill-achievability-compiler

# Install in development mode
pip install -e ".[dev]"

# Run tests
python3 -m pytest

# Build the paper (requires pdflatex + texlive)
cd paper
pdflatex skillachievability.tex && pdflatex skillachievability.tex
```

## Project Structure

- **`src/skillc/`** — the compiler package (checker, session types, pack model, front-ends)
- **`tests/`** — test suite (236 tests covering all major components)
- **`paper/`** — LaTeX source and built PDF with full proofs
- **`proof/`** — Coq verification of theorems (zero axioms)
- **`examples/`** — fixture skills for testing

## Key Components

### Checker (`src/skillc/checker.py`)
The trusted core: decides the four-premise achievability judgment using z3 for may-reachability.
- **Capability soundness**: no hallucinated tools
- **Realizability**: projection defined for every role
- **Conformance**: declared skills refine their contracts
- **Liveness**: goal may-reachable

### Session Types (`src/skillc/session.py`)
Projection, merge, and Gay-Hole subtyping for multiparty session types.
- Proj-Sel/Brn/Mrg rules
- Observed choice (Proj-Obs) for conversation-embedded selections
- Coinductive subtyping

### Front-ends
- **Markdown** (`frontend/markdown.py`): deterministic SKILL.md → pack compaction
- **LLM** (`frontend/llm.py`): semantic NL → pack distillation (untrusted, schema-gated)

## Testing

The test suite covers:
- Formula validation and schema gates
- Every refutation reason
- Projection, merge, and subtyping
- Loop semantics with numeric widening
- Autonomy boundary (spawn → UNKNOWN)
- Conformance (both directions)
- 15-spec ground-truth corpus (TP=6, FN=0, FP=2, TN=7)
- 6-spec extended corpus (decidable fragment, conformance)
- Markdown front-end extraction and profiles
- Bundle audit (security pre-pass)
- CLI and JSON output modes
- Real deployed skills (32 public skills, multiple profiles)

To run specific tests:
```bash
pytest tests/test_checker.py              # Core checker tests
pytest tests/test_session.py              # Session type tests
pytest tests/test_corpus_eval.py          # Corpus evaluation
pytest tests/test_real_skills.py          # Real skill tests (requires fetch)
```

## Documentation

- **README.md** — overview, quick start, what the checker decides
- **paper/skillachievability.tex** — full formal proofs and theoretical justification
- **docs/REAL_SKILLS_REPORT.md** — results on 32 deployed skills
- **docs/SEMANTIC_VALIDATION.md** — LLM compaction validation
- Code comments — only on non-obvious logic (why, not what)

## Conventions

- **Code style**: Python 3.8+, PEP 8
- **Comments**: Only on non-obvious logic; well-named identifiers are self-documenting
- **Commit messages**: Clear, descriptive; reference issues where relevant
- **Tests**: Unit tests for all public functions; integration tests for CLI
- **No comments on WHAT**: The code should be self-explanatory; only explain WHY when needed

## Soundness and Correctness

This project prioritizes **correctness by construction**:
- The checker's soundness is mechanized in Coq (zero axioms)
- Refutation verdicts are proofs relative to declared capabilities
- The SMT solver policy is conservative (UNKNOWN → satisfiable)
- Widening is always in the sound direction

If you make changes to the core checker logic, ensure:
1. The change preserves refutation soundness (T1)
2. It does not introduce false refutations of achievable goals
3. Tests pass, including the corpus confusion matrix

## Questions?

Feel free to open an issue with questions or discussions. We're happy to help!

---

Thank you for contributing to advancing formal verification of agent skills!
