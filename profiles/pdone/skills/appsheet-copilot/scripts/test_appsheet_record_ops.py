import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("appsheet_record_ops.py")
spec = importlib.util.spec_from_file_location("appsheet_record_ops", MODULE_PATH)
ops = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ops
spec.loader.exec_module(ops)


class FakeSchema:
    def __init__(self):
        self.columns = {
            "Case": {"CaseID", "Title", "Description", "Deadline", "Type", "Sub-Type", "Status", "Next Step Responsible Person"},
            "Case_Updates": {"CaseUpdateID", "CaseID", "Update Summary", "Update Description", "New Status", "New Next Step Responsible Person", "New Deadline", "Update Type", "Case Type", "Timestamp"},
            "HR_Employees": {"PersonID", "Name_ZH", "Name_EN", "Name_ZH_EN", "Appsheet Email", "Hidden"},
        }

    def column(self, table, name):
        return {"name": name} if name in self.columns[table] else None

    def slice_filter_selector(self, slice_name):
        return "Lookup", "Filter(Lookup, TRUE)"


class FakeClient:
    def __init__(self):
        self.calls = []
        self.case_rows = [
            {
                "CaseID": "C-20260521-AAA111",
                "Title": "Leaking air compressor",
                "Description": "Compressor fitting leak",
                "Status": "In Progress",
                "Type": "Case_General",
                "Deadline": "2026-05-22",
                "Next Step Responsible Person": "P-ERIC",
                "Latest_CaseUpdateID": "",
                "Last Updated": "2026-05-21 08:00:00",
            }
        ]
        self.people = [
            {"PersonID": "P-ERIC", "Name_EN": "Eric Liu", "Name_ZH": "劉", "Name_ZH_EN": "Eric Liu 劉", "Appsheet Email": "eric@example.com", "Hidden": False},
        ]

    def find(self, table, selector):
        self.calls.append(("Find", table, selector))
        if table == "Case":
            if "NOPE" in selector:
                return []
            return self.case_rows
        if table == "Case_Updates":
            return [{"CaseUpdateID": "C-U-NEW-123", "CaseID": "C-20260521-AAA111", "New Status": "Completed", "Timestamp": "05/21/2026 16:00:00"}]
        if table == "HR_Employees":
            return self.people
        return []

    def add(self, table, row):
        self.calls.append(("Add", table, row))
        result = dict(row)
        if table == "Case":
            result.setdefault("CaseID", "C-NEW-123")
        if table == "Case_Updates":
            result.setdefault("CaseUpdateID", "C-U-NEW-123")
        return [result]

    def edit(self, table, row):
        self.calls.append(("Edit", table, row))
        return [dict(row)]

    def action(self, table, action, rows=None, properties=None):
        self.calls.append(("Action", table, action, rows or [], properties or {}))
        return []


def planner(client=None):
    return ops.RecordOpsPlanner(schema=FakeSchema(), client=client)


def test_create_case_dry_run_builds_payload_and_requires_missing_fields():
    plan = planner().build("Create case title: Leaking air compressor; description: fitting is leaking; type: Case_General; responsible: Eric Liu; deadline: 2026-05-22")

    assert plan.intent == "create_case"
    assert plan.table == "Case"
    assert plan.row_payload["Title"] == "Leaking air compressor"
    assert plan.row_payload["Description"] == "fitting is leaking"
    assert plan.row_payload["Type"] == "Case_General"
    assert plan.row_payload["Deadline"] == "2026-05-22"
    assert plan.row_payload["Status"] == "Not Started"
    assert plan.dry_run_summary["will_create_parent"] is True


def test_add_case_update_executes_child_update_against_unique_case():
    client = FakeClient()
    plan = planner(client).build("Add update to case AAA111: vendor will arrive tomorrow; status: In Progress; responsible: Eric Liu", execute=True)

    assert plan.intent == "add_case_update"
    add_calls = [c for c in client.calls if c[0] == "Add" and c[1] == "Case_Updates"]
    assert len(add_calls) == 1
    payload = add_calls[0][2]
    assert payload["CaseID"] == "C-20260521-AAA111"
    assert payload["Update Summary"] == "vendor will arrive tomorrow"
    assert payload["Update Description"] == "vendor will arrive tomorrow"
    assert payload["New Status"] == "In Progress"
    assert payload["New Next Step Responsible Person"] == "P-ERIC"
    assert plan.execution["created_case_update_rows"][0]["CaseUpdateID"] == "C-U-NEW-123"


def test_close_case_creates_completed_case_update_and_runs_parent_sync_actions():
    client = FakeClient()
    plan = planner(client).build("Close case AAA111: replaced fitting and pressure checked", execute=True)

    assert plan.intent == "change_case_status"
    add_payload = [c[2] for c in client.calls if c[0] == "Add" and c[1] == "Case_Updates"][0]
    assert add_payload["New Status"] == "Completed"
    assert add_payload["Update Summary"] == "replaced fitting and pressure checked"
    assert "Timestamp" in add_payload
    action_names = [c[2] for c in client.calls if c[0] == "Action" and c[1] == "Case_Updates"]
    assert action_names == ["Case_Updates_UpdateCaseWithLatestCaseUpdateID", "Case_Updates_UpdateCaseInformationFromCaseUpdate"]
    assert not [c for c in client.calls if c[0] == "Edit" and c[1] == "Case"]
    assert "parent_case_readback" in plan.execution


def test_case_update_ambiguous_case_lookup_stops_with_choices():
    client = FakeClient()
    client.case_rows.append({**client.case_rows[0], "CaseID": "C-20260521-BBB222", "Title": "Second match"})

    plan = planner(client).build("Add update to case 20260521: check later", execute=True)

    assert plan.execution is None
    assert plan.clarifications[0].field == "CaseID"
    assert set(plan.clarifications[0].options) == {"C-20260521-AAA111", "C-20260521-BBB222"}


def test_appsheet_local_datetime_uses_taipei_wall_time():
    from datetime import datetime, timezone

    assert ops.appsheet_local_datetime(datetime(2026, 5, 21, 7, 42, 0, tzinfo=timezone.utc)) == "05/21/2026 15:42:00"


if __name__ == "__main__":
    import traceback

    failed = 0
    for name in sorted(n for n in globals() if n.startswith("test_")):
        try:
            globals()[name]()
        except BaseException as exc:
            failed += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=2)
        else:
            print(f"PASS {name}")
    print(f"failed {failed}")
    raise SystemExit(1 if failed else 0)
