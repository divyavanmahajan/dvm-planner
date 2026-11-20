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
| Buckets + tasks of a plan | `uvx dvm-planner tasks <planId or Planner URL> [-o file]` |
| Every listed plan | `uvx dvm-planner tasks --all -o all.json` |

Global options: `--port`, `--profile`, `--edge-path`.

## Workflow
1. Run the command, preferably with `-o file.json`, then filter the JSON with Python/jq rather than printing it all.
2. Plan id is the segment after `/plan/` in a Planner URL.
3. Task fields: `displayName`, `bucketId`, `percentComplete` (0/50/100), `status`, `priority`,
   `startUtcDateTime`, `dueUtcDateTime` (often null), `notes`, `checklist`, `links`,
   `userAssignments` (keys are Entra user object ids), `customFieldValues`, `planView.appliedCategoryIds`.
4. To filter by person: resolve the name to an object id (Microsoft Graph `/users?$search="displayName:..."`
   with the browser's Graph token, header `ConsistencyLevel: eventual`) and match against `userAssignments` keys.
5. Always report when `dueUtcDateTime` is empty instead of inventing dates. `plans` only covers
   recent/favorite plans, so say so when answering "all plans".

Tokens last ~1h and are recaptured on each run.
