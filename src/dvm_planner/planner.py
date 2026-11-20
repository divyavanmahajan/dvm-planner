"""Planner taskapi client (the same internal API the Planner web UI uses)."""

from __future__ import annotations

import httpx

BASE = "https://api.planner.svc.cloud.microsoft/taskapi/v4.0"
TASK_EXPAND = "checklist,links,userAssignments,customFieldValues"


class PlannerClient:
    def __init__(self, authorization: str):
        self.http = httpx.Client(
            headers={"Authorization": authorization, "Accept": "application/json"}, timeout=60
        )

    def _get_all(self, url: str) -> list[dict]:
        items: list[dict] = []
        while url:
            r = self.http.get(url)
            r.raise_for_status()
            data = r.json()
            items += data.get("value", [])
            url = data.get("@odata.nextLink")
        return items

    def list_plans(self) -> list[dict]:
        """Recent + favorite plans, de-duplicated by id."""
        plans: dict[str, dict] = {}
        for path in ("recentPlans", "favoritePlans"):
            for p in self._get_all(f"{BASE}/users('me')/{path}"):
                plans.setdefault(p["id"], p)
        return list(plans.values())

    def my_tasks(self) -> list[dict]:
        """Tasks assigned to the signed-in user, across all plans."""
        return self._get_all(f"{BASE}/users('me')/tasks?$expand={TASK_EXPAND}")

    def my_tasks_by_plan(self) -> list[dict]:
        names = {p["id"]: p.get("displayName") for p in self.list_plans()}
        grouped: dict[str, list[dict]] = {}
        for t in self.my_tasks():
            grouped.setdefault(t["planId"], []).append(t)
        return [
            {"id": pid, "displayName": names.get(pid) or self.get_plan(pid).get("displayName"),
             "taskCount": len(ts), "tasks": ts}
            for pid, ts in sorted(grouped.items(), key=lambda kv: -len(kv[1]))
        ]

    def get_plan(self, plan_id: str) -> dict:
        r = self.http.get(f"{BASE}/plans('{plan_id}')")
        r.raise_for_status()
        return r.json()

    def buckets(self, plan_id: str) -> list[dict]:
        return self._get_all(f"{BASE}/plans('{plan_id}')/buckets")

    def tasks(self, plan_id: str) -> list[dict]:
        return self._get_all(f"{BASE}/plans('{plan_id}')/tasks?$expand={TASK_EXPAND}")

    def plan_export(self, plan: dict) -> dict:
        pid = plan["id"]
        return {
            "id": pid,
            "displayName": plan.get("displayName"),
            "buckets": self.buckets(pid),
            "tasks": self.tasks(pid),
        }
