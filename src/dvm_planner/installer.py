"""Install the bundled agent skill for GitHub Copilot CLI and Claude Code."""

from __future__ import annotations

import shutil
from importlib.resources import as_file, files
from pathlib import Path

SKILL_NAME = "dvm-planner"
TARGETS = {
    "copilot": Path.home() / ".copilot" / "skills",
    "claude": Path.home() / ".claude" / "skills",
}


def update_skills(targets: list[str] | None = None) -> list[Path]:
    """Copy the bundled skill into each target's skills directory, replacing any old copy."""
    installed = []
    with as_file(files("dvm_planner") / "skills" / SKILL_NAME) as src:
        for name in targets or list(TARGETS):
            dest = TARGETS[name] / SKILL_NAME
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
            installed.append(dest)
    return installed
