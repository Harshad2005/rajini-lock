# Contributing to Rajini-Lock

PRs and issues are welcome. A few quick notes:

## Bug reports

Please include:
- macOS version + chip (Intel / Apple Silicon)
- Python version
- Output of `cat ~/Library/Application\ Support/RajiniLock/unlocker.log`
- What you tried, what happened, what you expected

## Feature ideas

Open an issue first so we can discuss scope. Big-ticket items already on the roadmap:

- SecurityAgent plug-in for *real* login replacement (Obj-C / Swift)
- Wake-word ("Hey Boss") instead of click-to-speak
- Anti-spoof / liveness detection
- Notarized `.dmg` installer

## Code style

- Format with `ruff format`
- Type hints on public functions
- Keep the UI module faithful to the film aesthetic — this is half the fun

## Testing

```bash
pip install -e .
pytest                    # (tests live in tests/, contributions welcome)
```

Don't push a branch that breaks the install script — that's how people get locked out of their Macs.

— *Sivaji-kku apparam yevan da?* 🙏
