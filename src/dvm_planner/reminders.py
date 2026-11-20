"""List my Planner tasks and create Outlook calendar reminders for selected ones."""

from __future__ import annotations

import re
import sys
from datetime import date, datetime

from .outlook import OutlookClient, planner_task_url, reminder_body
from .planner import PlannerClient


def candidates(client: PlannerClient, include_done: bool = False, include_no_due: bool = False) -> list[dict]:
    """My tasks as numbered rows sorted by due date (stable order so `--select` numbers are repeatable)."""
    names = {p["id"]: p.get("displayName") for p in client.list_plans()}
    rows = []
    for t in client.my_tasks():
        due = (t.get("dueDateTime") or {}).get("date")
        if (t.get("percentComplete") == 100 and not include_done) or (not due and not include_no_due):
            continue
        plan = names.get(t["planId"]) or client.get_plan(t["planId"]).get("displayName")
        names[t["planId"]] = plan
        tenant = (((t.get("creationInfo") or {}).get("createdBy") or {}).get("user") or {}).get("tenantId", "")
        rows.append({"id": t["id"], "title": t["displayName"], "plan": plan, "planId": t["planId"],
                     "due": due, "percentComplete": t.get("percentComplete", 0), "tenantId": tenant,
                     "task": t})
    rows.sort(key=lambda r: (r["due"] or "9999", r["title"].lower(), r["id"]))
    for i, r in enumerate(rows, 1):
        r["n"] = i
    return rows


def format_table(rows: list[dict]) -> str:
    return "\n".join(f"{r['n']:>3}  {r['due'] or '-':<10}  {r['percentComplete']:>3}%  {r['title'][:60]}  [{r['plan']}]"
                     for r in rows)


def parse_numbers(spec: str, count: int) -> set[int]:
    out: set[int] = set()
    for part in spec.replace(" ", "").split(","):
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not m:
            raise ValueError(f"bad selection {part!r}")
        lo, hi = int(m[1]), int(m[2] or m[1])
        out.update(range(lo, hi + 1))
    bad = [n for n in out if not 1 <= n <= count]
    if bad:
        raise ValueError(f"selection out of range 1-{count}: {sorted(bad)}")
    return out


def select(rows: list[dict], all_: bool, numbers: str | None, tasks: list[str]) -> list[dict]:
    if all_:
        return rows
    chosen: dict[str, dict] = {}
    if numbers:
        for n in parse_numbers(numbers, len(rows)):
            chosen[rows[n - 1]["id"]] = rows[n - 1]
    for q in tasks:
        hits = [r for r in rows if r["id"] == q] or [r for r in rows if q.lower() in r["title"].lower()]
        if len(hits) != 1:
            raise ValueError(f"{len(hits)} tasks match {q!r}"
                             + (": " + "; ".join(f"{r['n']} {r['title']}" for r in hits) if hits else ""))
        chosen[hits[0]["id"]] = hits[0]
    return sorted(chosen.values(), key=lambda r: r["n"])


def prompt_selection(rows: list[dict]) -> list[dict]:
    print(format_table(rows), file=sys.stderr)
    ans = input("Create reminders for (numbers like 1,3-5, 'all', blank to cancel): ").strip()
    if not ans:
        return []
    return rows if ans.lower() == "all" else select(rows, False, ans, [])


def create_reminders(outlook: OutlookClient, chosen: list[dict], *, at: str, duration: int,
                     reminder_minutes: int, on: str | None, show_as: str, dry_run: bool,
                     include_past: bool = False) -> list[dict]:
    hh, mm = (int(x) for x in at.split(":"))
    results = []
    for r in chosen:
        day = date.fromisoformat(on or r["due"] or "")
        start = datetime(day.year, day.month, day.day, hh, mm)
        subject = f"Planner: {r['title']}"
        res = {"taskId": r["id"], "title": r["title"], "subject": subject, "start": start.isoformat()}
        if start < datetime.now() and not include_past:
            res["status"] = "skipped (date in the past)"
        elif outlook.find_by_subject(day, subject):
            res["status"] = "skipped (already exists)"
        elif dry_run:
            res["status"] = "dry-run"
        else:
            link = planner_task_url(r["planId"], r["id"], r["tenantId"])
            outlook.create_event(subject, reminder_body(r["task"], r["plan"], link), start, duration,
                                 reminder_minutes, show_as)
            res["status"] = "created"
        results.append(res)
    return results
