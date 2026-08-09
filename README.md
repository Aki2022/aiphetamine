# AIphetamine

AIphetamine is an experimental macOS menu-bar companion for Claude Code. It
records sanitized local Hook events, lets you explicitly opt in to sessions,
and can invoke the official non-interactive resume command at the next fixed
two-hour boundary.

> AIphetamine is not affiliated with Anthropic. It does not guarantee that a
> resumed Claude Code process will continue the original task successfully.

## What it does

- Detects Claude Code candidate and rate-limit events through local Hooks.
- Shows identifiable sessions in a macOS menu-bar menu with native checkmarks.
- Runs only for sessions explicitly checked by the operator.
- Routes `main` and `alias` through separate `CLAUDE_CONFIG_DIR` values.
- Invokes Claude Code with the fixed message `Continue` using `-p --resume`.
- Schedules one poll at the next even-hour boundary and reports sanitized
  aggregate results in the menu.
- Stores local event records and seven-day rotated operational logs without
  storing prompts, transcripts, or Claude stdout/stderr.

The resume process is headless. It does not open or control an existing
interactive Claude Code window.

## Status

This repository is an experimental source-tree prototype. The core runtime,
Hook lifecycle, account routing, menu behavior, fixed-boundary scheduler, and
local verification suite are implemented. Packaging, installation automation,
and a released application bundle are not provided.

Natural rate-limit behavior and continuation of arbitrary Claude Code work are
environment-dependent and are not treated as guaranteed product behavior.

## Requirements

- macOS
- Python 3
- PyObjC/AppKit for the menu-bar process
- Claude Code installed and authenticated separately for each account used
- An owner-controlled executable configuration accepted by the runtime

No Claude credentials, tokens, or account identifiers belong in this
repository.

## Verify locally

From the repository root:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q src hooks scripts
python3 scripts/run_dry_cycle.py
```

The dry-run command reads local AIphetamine state and prints only sanitized
counts. It does not launch Claude, modify settings, or persist selection state;
it may create or update the local operational log directory.

## Hook setup

Generate a settings fragment without editing an existing Claude Code settings
file:

```bash
python3 scripts/generate_hook_config.py \
  --hook-command 'python3 /absolute/path/to/hooks/aiphetamine_hook.py' \
  --account-name main
```

Review the generated JSON and merge it manually into the intended Claude Code
settings file. The generator parses the command into argv tokens, rejects shell
metacharacters, and quotes each token before adding Hook arguments.
`--account-name` accepts only `main` or `alias`. For the second
isolated account, generate a separate fragment with `--account-name alias` and
use `~/.claude-seat2` as that account's `CLAUDE_CONFIG_DIR`.

See [docs/guides/hook-setup.md](docs/guides/hook-setup.md) for the safety
boundary and removal procedure. The generator never edits existing settings.

## Running the menu-bar source tree

The source-tree entry point is:

```bash
python3 scripts/run_menubar.py
```

For long-running use, generate and manually review a LaunchAgent plist as
described in [docs/guides/production-integration.md](docs/guides/production-integration.md).
Registration is an explicit operator action; this repository does not silently
install or modify unrelated LaunchAgents.

## Data and privacy

By default, local runtime data is kept under
`~/.local/share/aiphetamine/`. Candidate and rate-limit records contain the
session ID, absolute project path, optional display names, and the allowlisted
account label needed for local eligibility and account routing. Operational
logs are sanitized and do not contain those raw record values. The runtime
does not intentionally persist prompts, transcripts, authentication values,
or Claude process output.

Before sharing diagnostics, inspect them for local project names and paths.
Do not commit runtime data, Claude settings, credentials, or generated local
configuration files.

## Documentation

- [Product requirements](docs/specs/PRD.md)
- [Architecture](docs/specs/architecture.md)
- [Resume wiring guide](docs/guides/resume-wiring.md)
- [Hook setup guide](docs/guides/hook-setup.md)
- [Runtime dry-run guide](docs/guides/runtime-core-dry-run.md)
- [Documentation index](docs/00_index.md)

## License

This project is released under the [MIT License](LICENSE). Claude Code and
Anthropic remain separate products and trademarks.
