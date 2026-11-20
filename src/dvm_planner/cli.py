"""Export Microsoft Planner plans and tasks as JSON via an Edge browser (CDP)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import __version__
from .browser import API_HOST, DEFAULT_PORT, DEFAULT_PROFILE, capture_outlook, capture_tokens, launch_edge
from .outlook import OutlookClient
from .reminders import candidates, create_reminders, format_table, prompt_selection, select, sync_reminders
from .planner import GRAPH_HOST, PlannerClient
from .installer import update_skills


def _plan_id(value: str) -> str:
    m = re.search(r"/plan/([^/?#]+)", value)
    return m.group(1) if m else value


def _client(args) -> PlannerClient:
    launch_edge(args.port, args.profile, args.edge_path)
    tokens = capture_tokens(args.port, (API_HOST, GRAPH_HOST))
    return PlannerClient(tokens[API_HOST], tokens[GRAPH_HOST])


def _emit(data, out: str | None):
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if out:
        Path(out).write_text(text, encoding="utf-8")
        print(f"wrote {out}", file=sys.stderr)
    else:
        print(text)


def _remind(args, p) -> int:
    rows = candidates(_client(args), args.include_done, args.include_no_due)
    public = [{k: v for k, v in r.items() if k not in ("task", "tenantId")} for r in rows]
    if args.sync:
        auth, anchor = capture_outlook(args.port)
        _emit(sync_reminders(OutlookClient(auth, anchor), rows, reminder_minutes=args.reminder_minutes,
                             show_as=args.show_as, dry_run=args.dry_run), None)
        return 0
    if args.list:
        if args.json:
            _emit(public, None)
        else:
            print(format_table(rows))
        return 0
    try:
        if args.all or args.select or args.task:
            chosen = select(rows, args.all, args.select, args.task)
        elif sys.stdin.isatty():
            chosen = prompt_selection(rows)
        else:
            p.error("non-interactive: give --all, --select or --task (use --list first)")
    except ValueError as e:
        p.error(str(e))
    if not chosen:
        print("nothing selected", file=sys.stderr)
        return 0
    if (args.include_no_due and not args.on) and any(not r["due"] for r in chosen):
        p.error("tasks without a due date need --on YYYY-MM-DD")
    auth, anchor = capture_outlook(args.port)
    results = create_reminders(OutlookClient(auth, anchor), chosen, at=args.at, duration=args.duration,
                               reminder_minutes=args.reminder_minutes, on=args.on, show_as=args.show_as,
                               dry_run=args.dry_run, include_past=args.include_past)
    _emit(results, None)
    return 0


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
    rm = sub.add_parser("remind", help="List my tasks and create Outlook calendar reminders for selected ones")
    rm.add_argument("--list", action="store_true", help="Only list candidate tasks (numbered)")
    rm.add_argument("--all", action="store_true", help="Create reminders for all listed tasks")
    rm.add_argument("--select", metavar="N,M-K", help="Numbers from --list (stable order by due date)")
    rm.add_argument("--task", action="append", default=[], help="Task id or title fragment (repeatable)")
    rm.add_argument("--include-done", action="store_true", help="Include 100%% complete tasks")
    rm.add_argument("--include-no-due", action="store_true", help="Include tasks without a due date (needs --on)")
    rm.add_argument("--on", metavar="YYYY-MM-DD", help="Event date (default: the task's due date)")
    rm.add_argument("--at", default="09:00", metavar="HH:MM", help="Event start time (default 09:00)")
    rm.add_argument("--duration", type=int, default=30, help="Event minutes (default 30)")
    rm.add_argument("--reminder-minutes", type=int, default=1440, help="Reminder before start (default 1440 = 1 day)")
    rm.add_argument("--show-as", default="Busy", choices=["Busy", "Free", "Tentative", "OOF"])
    rm.add_argument("--include-past", action="store_true", help="Create events even if the date has passed")
    rm.add_argument("--sync", action="store_true",
                    help="Move existing 'Planner: <task>' events to the task's current due date")
    rm.add_argument("--dry-run", action="store_true")
    rm.add_argument("--json", action="store_true", help="JSON output for --list")
    ut = sub.add_parser("usertasks", help="Tasks assigned to another person (name or e-mail)")
    ut.add_argument("user")
    ut.add_argument("--plan", action="append", help="Limit to plan id/URL (repeatable)")
    ut.add_argument("--with-due", action="store_true", help="Only tasks that have a due date")
    ut.add_argument("-o", "--output")
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
    if args.cmd == "remind":
        return _remind(args, p)
    client = _client(args)
    if args.cmd == "plans":
        _emit([{"id": x["id"], "displayName": x.get("displayName"),
                "lastModifiedDateTime": x.get("lastModifiedDateTime")}
               for x in client.list_plans()], args.output)
    elif args.cmd == "usertasks":
        users = client.find_users(args.user)
        if len(users) != 1:
            p.error(f"{len(users)} users match {args.user!r}: "
                    + "; ".join(f"{u['displayName']} <{u['mail']}>" for u in users))
        tasks = client.user_tasks(users[0]["id"], [_plan_id(x) for x in args.plan] if args.plan else None)
        if args.with_due:
            tasks = [t for t in tasks if (t.get("dueDateTime") or {}).get("date")]
        tasks.sort(key=lambda t: ((t.get("dueDateTime") or {}).get("date") or "9999", t["displayName"]))
        _emit({"user": users[0], "taskCount": len(tasks), "tasks": tasks}, args.output)
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
