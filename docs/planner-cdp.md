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
`startUtcDateTime`, `dueUtcDateTime`, `notes` (html), `creationInfo`, `lastModifiedBy`,
`planView.appliedCategoryIds` (labels), plus expanded `checklist`, `links`, `userAssignments`,
`customFieldValues`. Tokens expire after ~1h; recapture by reloading the tab.

## 5. Automation
`dvm-planner` implements these steps: `launch`, `plans`, `tasks`.
