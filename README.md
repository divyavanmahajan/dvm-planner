# dvm-planner

`dvm-planner` extracts **Microsoft Planner** data (plans, buckets, tasks, assignees, due dates,
checklists) as JSON. It launches Microsoft Edge with Chrome DevTools Protocol (CDP) enabled, reuses your
signed-in Planner session to obtain the token the Planner web UI itself uses, and queries Planner's
`taskapi` directly. No app registration or admin consent is needed - only a browser signed in to Planner.

It also ships an **agent skill** so GitHub Copilot CLI and Claude Code can answer questions like
"which tasks are assigned to me?" or "list my plans" by running the tool for you.

## Requirements
- Microsoft Edge
- [uv](https://docs.astral.sh/uv/) (for `uvx`), Python 3.10+

## Usage
```
uvx dvm-planner launch                      # start Edge (CDP port 19222, profile ~/.dvm-planner/edge-profile)
uvx dvm-planner plans                       # list plans (recent + favorites)
uvx dvm-planner mytasks [--summary]         # tasks assigned to me, grouped by plan
uvx dvm-planner tasks <planId|URL>          # buckets + tasks of one plan
uvx dvm-planner tasks --all -o all.json     # every listed plan
```
Options: `--port`, `--profile`, `--edge-path`, `-o/--output`. On first run sign in to Planner in the
Edge window that opens (SSO usually works automatically); the profile is reused afterwards.

Notes: `plans` covers recent/favorite plans only; `dueUtcDateTime` is often empty in Planner data;
tokens last about an hour and are recaptured on each run.
How it works: [docs/planner-cdp.md](docs/planner-cdp.md).

## Use with GitHub Copilot CLI
```
uvx dvm-planner --update-skills copilot     # installs to ~/.copilot/skills/dvm-planner
```
Restart/reload Copilot CLI, then ask e.g. *"List the tasks assigned to me in Planner"*; the
`dvm-planner` skill is picked up automatically.

## Use with Claude Code
```
uvx dvm-planner --update-skills claude      # installs to ~/.claude/skills/dvm-planner
```
Start a new Claude Code session and ask the same kind of question.

`uvx dvm-planner --update-skills` (no value) installs for both. Re-run it after upgrading
(`uvx dvm-planner@latest --update-skills`) to refresh the skill.

## Development & releases
Skill source: `src/dvm_planner/skills/dvm-planner/SKILL.md` (bundled in the wheel).
Every push to `main` tags the next `vX.Y.Z` and publishes to PyPI via Trusted Publishing
(one-time setup: PyPI trusted publisher for this repo, workflow `release.yml`, environment `pypi`).
The version is derived from git tags (hatch-vcs).

### Keeping docs current (required)
On every major change (new/changed command or option, new data source/endpoint, packaging or release
change) update **in the same commit**: this README, `docs/planner-cdp.md`, and the skill
`src/dvm_planner/skills/dvm-planner/SKILL.md`. These rules are also in `AGENTS.md`.
