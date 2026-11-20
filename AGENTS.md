# Contributor / agent instructions

- On every major change (new or changed command/option, new endpoint or data source, packaging/release
  change), update in the same commit: `README.md`, `docs/planner-cdp.md`, and
  `src/dvm_planner/skills/dvm-planner/SKILL.md`.
- Commit messages must not name Copilot or Claude as author/co-author (no `Co-authored-by` trailers for them).
- Releases are automatic on push to `main` (see `.github/workflows/release.yml`); do not tag manually.
