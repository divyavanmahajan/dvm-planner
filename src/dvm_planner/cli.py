"""Export Microsoft Planner plans and tasks as JSON via an Edge browser (CDP)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import __version__
from .browser import DEFAULT_PORT, DEFAULT_PROFILE, capture_token, launch_edge
from .planner import PlannerClient
from .installer import update_skills


def _plan_id(value: str) -> str:
    m = re.search(r"/plan/([^/?#]+)", value)
    return m.group(1) if m else value


def _client(args) -> PlannerClient:
    launch_edge(args.port, args.profile, args.edge_path)
    return PlannerClient(capture_token(args.port))


def _emit(data, out: str | None):
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if out:
        Path(out).write_text(text, encoding="utf-8")
        print(f"wrote {out}", file=sys.stderr)
    else:
        print(text)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="dvm-planner", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--port", type=int, default=DEFAULT_PORT, help="CDP port")
    p.add_argument("--profile", type=Path, default=DEFAULT_PROFILE, help="Edge user-data-dir")
    p.add_argument("--edge-path", help="Path to msedge executable")
    p.add_argument("--update-skills", nargs="?", const="all", choices=["all", "copilot", "claude"],
                   metavar="{all,copilot,claude}",
                   help="Install/refresh the dvm-planner skill for GitHub Copilot and/or Claude Code")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("launch", help="Start Edge with CDP enabled and open Planner")
    pl = sub.add_parser("plans", help="List plans as JSON")
    pl.add_argument("-o", "--output")
    mt = sub.add_parser("mytasks", help="Tasks assigned to me, grouped by plan (JSON)")
    mt.add_argument("-o", "--output")
    mt.add_argument("--summary", action="store_true", help="Only plan names and task counts")
    u = sub.add_parser("update-task", help="Update a task (due date, notes, checklist, comment)")
    u.add_argument("task", help="Task id, or part of the title of one of my tasks")
    u.add_argument("--due", metavar="YYYY-MM-DD|none", help="Set or clear the due date")
    u.add_argument("--notes", help="Replace notes (HTML)")
    u.add_argument("--add-checklist", action="append", default=[], metavar="TEXT")
    u.add_argument("--comment", help="Post a comment")
    u.add_argument("--patch", metavar="JSON", help="Raw PATCH body, as sent by the Planner UI")
    t = sub.add_parser("tasks", help="Export plan tasks (with buckets) as JSON")
    t.add_argument("plan", nargs="*", help="Plan ids or Planner URLs; omit with --all")
    t.add_argument("--all", action="store_true", help="Export every listed plan")
    t.add_argument("-o", "--output")

    args = p.parse_args(argv)
    if args.update_skills:
        targets = None if args.update_skills == "all" else [args.update_skills]
        for d in update_skills(targets):
            print(f"installed skill -> {d}")
        return 0
    if not args.cmd:
        p.error("a command is required (launch, plans, mytasks, tasks) or --update-skills")
    if args.cmd == "launch":
        started = launch_edge(args.port, args.profile, args.edge_path)
        print("started Edge" if started else "CDP already available", f"on port {args.port}")
        return 0

    if args.cmd == "tasks" and not args.all and not args.plan:
        p.error("give plan ids/URLs or --all")
    client = _client(args)
    if args.cmd == "plans":
        _emit([{"id": x["id"], "displayName": x.get("displayName"),
                "lastModifiedDateTime": x.get("lastModifiedDateTime")}
               for x in client.list_plans()], args.output)
    elif args.cmd == "update-task":
        task_id = args.task
        if not re.fullmatch(r"[\w-]{20,}", task_id):
            hits = client.find_my_tasks(task_id)
            if len(hits) != 1:
                p.error(f"{len(hits)} of my tasks match {task_id!r}: "
                        + "; ".join(f"{t['displayName']} ({t['id']})" for t in hits))
            task_id = hits[0]["id"]
        if args.due:
            if args.due != "none" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.due):
                p.error("--due must be YYYY-MM-DD or none")
            client.set_due_date(task_id, None if args.due == "none" else args.due)
        if args.notes:
            client.set_notes(task_id, args.notes)
        for item in args.add_checklist:
            client.add_checklist_item(task_id, item)
        if args.patch:
            client.patch_task(task_id, json.loads(args.patch))
        if args.comment:
            client.add_comment(task_id, args.comment)
        _emit(client.get_task(task_id), None)
    elif args.cmd == "mytasks":
        data = client.my_tasks_by_plan()
        if args.summary:
            data = [{k: v for k, v in x.items() if k != "tasks"} for x in data]
        _emit(data, args.output)
    else:
        plans = client.list_plans() if args.all else [client.get_plan(_plan_id(x)) for x in args.plan]
        _emit([client.plan_export(x) for x in plans], args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
