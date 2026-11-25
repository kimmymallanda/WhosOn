# WhosOn

A co-captain for adult league tennis teams: it texts every player, builds a valid and fair lineup, and finds the sub at 9pm.

Start with `CLAUDE.md` for project context, architecture and the course plan.

```bash
pip install -r requirements.txt
pytest -q
```

## Layout
- `docs/`: PRD (Word copy)
- `data/`: synthetic roster, schedule, sample league config and rules, labeled replies
- `src/rules_checker.py`: deterministic lineup checker (rule IDs R1–R6)
- `prompts/`: LLM prompts (availability parser first)
- `evals/`: scoring scripts
- `tests/`: unit tests
