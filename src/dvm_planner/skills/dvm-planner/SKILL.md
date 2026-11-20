---
name: dvm-planner
description: Read Microsoft Planner plans, buckets and tasks (including tasks assigned to me, assignees, due dates, checklists) as JSON using the dvm-planner CLI, which drives a signed-in Edge browser over CDP. Use when asked to list planners/plans, list or analyse Planner tasks, find tasks by assignee or due date, or export Planner data.
---

# dvm-planner

`dvm-planner` exports Microsoft Planner data as JSON. It starts Edge with a remote-debugging port
(default 19222, profile `~/.dvm-planner/edge-profile`), reads the bearer token the Planner web UI
uses, and calls the Planner `taskapi` directly. The user must be signed in to Planner in that Edge
profile (SSO normally works automatically; otherwise ask them to sign in once in the launched window).

## Commands (run with `uvx dvm-planner ...`)

| Goal | Command |
|---|---|
| Start Edge with CDP | `uvx dvm-planner launch` |
| List plans (recent + favorite) | `uvx dvm-planner plans [-o plans.json]` |
| Tasks assigned to me, by plan | `uvx dvm-planner mytasks [--summary] [-o file]` |
| Tasks assigned to someone else | `uvx dvm-planner usertasks "<name or e-mail>" [--with-due] [--plan <id/URL>] [-o file]` |
| Buckets + tasks of a plan | `uvx dvm-planner tasks <planId or Planner URL> [-o file]` |
| Every listed plan | `uvx dvm-planner tasks --all -o all.json` |
| Update a task | `uvx dvm-planner update-task <taskId or title fragment> [--due YYYY-MM-DD\|none] [--notes HTML] [--add-checklist TEXT] [--comment TEXT] [--patch JSON]` |

| List candidate tasks for reminders | `uvx dvm-planner remind --list [--json]` |
| Create Outlook reminders | `uvx dvm-planner remind (--all \| --select 1,3-5 \| --task <id/title>)... [--at HH:MM] [--duration 30] [--reminder-minutes 1440] [--on YYYY-MM-DD] [--show-as Busy] [--dry-run]` |
| Re-date reminders after due dates changed | `uvx dvm-planner remind --sync [--dry-run]` |

Global options: `--port`, `--profile`, `--edge-path`.

## Calendar reminders (creates real calendar events)
`remind` makes an Outlook event `Planner: <task title>` on each task's due date (default 09:00, 30 min,
reminder 1 day before, body has plan, bucket and a task link). Never prompts when stdin is not a TTY:
1. `remind --list --json` (my tasks, not complete, with due date; `n` is stable, sorted by due date).
2. Confirm the selection with the user, run once with `--dry-run`, then run without it with
   `--all`, `--select`, or `--task`. Past dates and events that already exist are skipped (idempotent).
3. Needs an Outlook calendar tab signed in in the same Edge profile (opened automatically).
Tasks without a due date need `--include-no-due --on YYYY-MM-DD`.
After changing a task's due date (e.g. with `update-task --due`), run `remind --sync --dry-run` then `remind --sync`:
each `Planner: <title>` event whose date differs from the due date is moved (same time and duration).

`usertasks` resolves the person via Microsoft Graph (errors listing candidates if the name is
ambiguous; then retry with the e-mail). Planner has no per-user endpoint for other people, so it scans
recent/favorite plans plus plans holding your own tasks; use `--plan` to scan specific plans.

## Updating tasks (writes change real data)
1. Identify the exact task first (`mytasks`/`usertasks`/`tasks`) and show the user the task, plan and
   the change. Get confirmation before writing unless the user's request was already explicit.
2. Run `update-task`. A title fragment must match exactly one of *my* tasks, otherwise pass the task id.
   `update-task` prints the updated task; verify the change in that output.
3. Typical edits:
   - Due date: `--due 2026-12-31` (clear with `--due none`). Stored as `dueDateTime.date`.
   - Notes: `--notes "<div>html</div>"` replaces the whole description.
   - Checklist: `--add-checklist "text"` (repeatable).
   - Comment: `--comment "text"` posts to the task conversation.
4. For anything else (title, percent complete, assignees, bucket, labels, start date) use `--patch` with the raw
   JSON body the Planner UI sends, e.g. `--patch '{"dueDateTime":{"date":"2026-12-31"}}'`. If you don't know the
   body, capture it: attach CDP to the Planner tab (`Network.enable`), have the user perform the action once in
   the UI, and read the non-GET requests to `api.planner.svc.cloud.microsoft` (`request.postData`).
   Details and examples: `docs/planner-cdp.md` section 5. Do not guess field names: unknown fields can return 200
   yet change nothing (e.g. `dueUtcDateTime` is ignored on write), so always re-read the task to confirm.
5. Writes need the task's current ETag (`If-Match`) and `OData-Version: 4.01`; the tool handles both. An HTTP
   412 means the task changed meanwhile; re-run.

## Workflow
1. Run the command, preferably with `-o file.json`, then filter the JSON with Python/jq rather than printing it all.
2. Plan id is the segment after `/plan/` in a Planner URL.
3. Task fields: `displayName`, `bucketId`, `percentComplete` (0/50/100), `status`, `priority`,
   `startDateTime`, `dueDateTime` (`.date`; null when unset), `notes`, `checklist`, `links`,
   `userAssignments` (list of `{id}` = Entra user object id without dashes), `customFieldValues`, `planView.appliedCategoryIds`.
4. To filter by person: run `usertasks "<name>"` (resolves the user via Graph and filters `userAssignments`).
   For custom logic, resolve the name to an object id (Graph `/users?$search="displayName:..."`,
   header `ConsistencyLevel: eventual`) and match against `userAssignments[].id` (strip dashes).
5. Always report when `dueDateTime` is empty instead of inventing dates. `plans` only covers
   recent/favorite plans, so say so when answering "all plans".

Tokens last ~1h and are recaptured on each run.
