"""Create Outlook calendar reminders through Outlook on the web's own OWA JSON API."""

from __future__ import annotations

import html
from datetime import date, datetime, timedelta

import httpx

SERVICE = "https://outlook.cloud.microsoft/owa/service.svc"
TZ = "W. Europe Standard Time"
FMT = "%Y-%m-%dT%H:%M:%S.000"


def planner_task_url(plan_id: str, task_id: str, tenant_id: str) -> str:
    return f"https://planner.cloud.microsoft/webui/plan/{plan_id}/view/board/task/{task_id}?tid={tenant_id}"


class OutlookClient:
    def __init__(self, authorization: str, anchor: str, timezone: str = TZ):
        self.tz = timezone
        self.headers = {"Authorization": authorization, "X-AnchorMailbox": anchor,
                        "Content-Type": "application/json; charset=utf-8",
                        "Prefer": 'IdType="ImmutableId"'}

    def _call(self, action: str, body: dict) -> dict:
        req = {"Header": {"__type": "JsonRequestHeaders:#Exchange", "RequestServerVersion": "V2018_01_08",
                          "TimeZoneContext": {"__type": "TimeZoneContext:#Exchange",
                                              "TimeZoneDefinition": {"__type": "TimeZoneDefinitionType:#Exchange",
                                                                     "Id": self.tz}}},
               "Body": body}
        r = httpx.post(f"{SERVICE}?action={action}&app=Calendar", json=req, timeout=60,
                       headers={**self.headers, "Action": action})
        r.raise_for_status()
        return r.json()["Body"]

    def events_between(self, first: date, last: date) -> list[dict]:
        """Events starting on first..last inclusive."""
        body = self._call("FindItem", {
            "__type": "FindItemRequest:#Exchange",
            "ItemShape": {"__type": "ItemResponseShape:#Exchange", "BaseShape": "Default"},
            "CalendarView": {"__type": "CalendarView:#Exchange", "StartDate": first.strftime(FMT),
                             "EndDate": (last + timedelta(days=1)).strftime(FMT)},
            "ParentFolderIds": [{"__type": "DistinguishedFolderId:#Exchange", "Id": "calendar"}],
            "Traversal": "Shallow"})
        items = body["ResponseMessages"]["Items"][0]["RootFolder"]["Items"]
        # the service may return more than the requested window, so filter by start date
        return [i for i in items if first.isoformat() <= str(i.get("Start", ""))[:10] <= last.isoformat()]

    def events_on(self, day: date) -> list[dict]:
        return self.events_between(day, day)

    def find_by_subject(self, day: date, subject: str) -> dict | None:
        return next((e for e in self.events_on(day) if e.get("Subject") == subject), None)

    def create_event(self, subject: str, body_html: str, start: datetime, minutes: int,
                     reminder_minutes: int, show_as: str = "Busy") -> dict:
        item = {"__type": "CalendarItem:#Exchange", "Subject": subject,
                "Body": {"BodyType": "HTML", "Value": body_html},
                "Start": start.strftime(FMT), "End": (start + timedelta(minutes=minutes)).strftime(FMT),
                "StartTimeZoneId": self.tz, "EndTimeZoneId": self.tz, "IsAllDayEvent": False,
                "FreeBusyType": show_as, "ReminderIsSet": True,
                "ReminderMinutesBeforeStart": reminder_minutes, "Sensitivity": "Normal",
                "IsResponseRequested": True}
        body = self._call("CreateCalendarEvent", {
            "__type": "CreateItemRequest:#Exchange", "Items": [item],
            "SavedItemFolderId": {"__type": "TargetFolderId:#Exchange",
                                  "BaseFolderId": {"__type": "DistinguishedFolderId:#Exchange", "Id": "calendar"}},
            "ItemShape": {"__type": "ItemResponseShape:#Exchange", "BaseShape": "IdOnly"},
            "SendMeetingInvitations": "SendToNone"})
        msg = body["ResponseMessages"]["Items"][0]
        if msg.get("ResponseClass") not in (None, "Success"):
            raise RuntimeError(msg.get("MessageText") or str(msg))
        return msg["Items"][0]["ItemId"]

    def delete_event(self, item_id: dict) -> None:
        self._call("DeleteItem", {
            "__type": "DeleteItemRequest:#Exchange",
            "ItemIds": [{"__type": "ItemId:#Exchange", "Id": item_id["Id"], "ChangeKey": item_id.get("ChangeKey")}],
            "DeleteType": "MoveToDeletedItems", "SendMeetingCancellations": "SendToNone"})


def reminder_body(task: dict, plan_name: str, link: str) -> str:
    due = (task.get("dueDateTime") or {}).get("date") or "-"
    return (f'<div>Planner task: <a href="{html.escape(link)}">{html.escape(task["displayName"])}</a></div>'
            f"<div>Plan: {html.escape(plan_name or '')}</div>"
            f"<div>Due: {due} &middot; Progress: {task.get('percentComplete', 0)}%</div>")
