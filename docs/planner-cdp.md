# Reading Microsoft Planner tasks through the browser (CDP)

## 1. Start Edge with CDP
A separate profile folder is required (Edge ignores the debug port for the default profile):

```powershell
msedge --remote-debugging-port=19222 --user-data-dir=<folder>\edge-profile --remote-allow-origins=* `
  "https://planner.cloud.microsoft/ui/web/plan/<planId>/view/board?tid=<tenantId>"
```
SSO signs in automatically; otherwise sign in once (profile persists).
`http://127.0.0.1:19222/json/list` lists tabs with their `webSocketDebuggerUrl`.

## 2. Discover the API
Connect to the Planner page websocket, send `Network.enable` then `Page.reload`, and watch
`Network.requestWillBeSent`. The UI calls a private OData API:

`https://api.planner.svc.cloud.microsoft/taskapi/v4.0`

with header `Authorization: Bearer <token>` (the token is not stored in a readable cookie; read it from the
request headers of any call to that host). Other hosts (graph.microsoft.com, project.microsoft.com) get their
own tokens, which do **not** work for taskapi.

## 3. Endpoints
| Purpose | Request |
|---|---|
| Plans (recent) | `GET /users('me')/recentPlans` |
| Plans (favorites) | `GET /users('me')/favoritePlans` |
| One plan | `GET /plans('{planId}')` (`?$expand=planView/categories,links,contexts` adds labels) |
| Buckets | `GET /plans('{planId}')/buckets` |
| Tasks | `GET /plans('{planId}')/tasks?$expand=checklist,links,userAssignments,customFieldValues` |
| Custom fields | `GET /plans('{planId}')/customFieldDefinitions?$expand=choiceOptions` |
| Goals | `GET /plans('{planId}')/goals` |

Notes: `/users('me')/plans` and `/plans` without a filter fail (404/405). Responses are paged with
`@odata.nextLink`. Plan id is the segment after `/plan/` in the UI URL.

## 4. Task fields
Each task includes `id`, `displayName`, `bucketId`, `percentComplete`, `status`, `priority`,
`startDateTime`, `dueDateTime`, `notes` (html), `creationInfo`, `lastModifiedBy`,
`planView.appliedCategoryIds` (labels), plus expanded `checklist`, `links`, `userAssignments`,
`customFieldValues`. Tokens expire after ~1h; recapture by reloading the tab.

## 5. Writing: capture what the UI sends
Guessing write payloads fails silently (e.g. PATCHing `dueUtcDateTime` returns 200 but changes nothing).
Record the real calls instead: attach CDP to the Planner tab, `Network.enable`, and log every
non-GET request to `api.planner.svc.cloud.microsoft` with `request.postData` while you perform the action in the UI.
Writes need headers `If-Match: <task @odata.etag>` (GET the task first), `OData-Version: 4.01`,
`Content-Type: application/json`, and `Prefer: return=representation`.

| Action | Request (all under `/taskapi/v4.0`) |
|---|---|
| Set due date | `PATCH /tasks('{id}')?$expand=checklist,links,userAssignments,customFieldValues` body `{"dueDateTime":{"date":"2026-12-18"}}` (`null` clears) |
| Notes | same PATCH, `{"notes":{"content":"<div>..</div>","contentType":"html"}}` |
| Add checklist item | same PATCH, `{"checklist@delta":[{"displayName":"..","isChecked":false,"orderHint":" <9223372036854775807 - .NET ticks>P,!"}]}` |
| Comment | `POST /tasks('{id}')/messages` `{"messageType":"richTextHtml","content":"<div>..</div>","properties":{"mentions":[]}}` |

`timeZone` is read-only. Read and write both use `dueDateTime` (`{date, time, timezone, isTimeSpecified}`); `dueUtcDateTime` is legacy and is usually null.

## 6. Automation
`dvm-planner` implements these steps: `launch`, `plans`, `mytasks`, `tasks`, `update-task`.

