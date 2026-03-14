"""
Test ADO Activities — Verify the payloads being sent through the pipeline.

This script directly calls the activity functions (without Temporal)
to verify that each step produces the correct data.

Usage:
  cd d:\aubrant\LoL\backend
  conda activate aubrant
  python test_activities.py
"""

import asyncio
import json
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv(".env")

from ado.client import (
    query_pending_bundles,
    get_linked_test_cases,
    extract_test_payload,
    get_app_url_for_test_case,
    get_source_infra_from_bundle,
    get_work_items_batch,
)


def section(title, num):
    print()
    print("=" * 70)
    print(f"  ACTIVITY TEST {num}: {title}")
    print("=" * 70)


def dump(label, data, max_len=500):
    """Pretty print JSON data with truncation."""
    text = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    if len(text) > max_len:
        text = text[:max_len] + f"\n  ... (truncated, total {len(text)} chars)"
    print(f"  {label}:")
    for line in text.split("\n"):
        print(f"    {line}")


async def main():
    print()
    print("=" * 70)
    print("  ADO ACTIVITIES PAYLOAD VERIFICATION")
    print("  Directly calling activity functions to check data flow")
    print("=" * 70)

    # ── Test 1: poll_pending_bundles ──────────────────────────────

    section("poll_pending_bundles()", 1)
    print("  This is what the PollerWorkflow calls to find new bundles.")
    print()

    bundles = await query_pending_bundles()
    print(f"  Found: {len(bundles)} pending bundle(s)")
    print()

    if not bundles:
        print("  [!] No pending bundles found. Create one from the dashboard first,")
        print("      or manually create a Task in ADO with:")
        print("        - Tags: RegressionBundle")
        print("        - State: New")
        print("        - Link to Test Cases via Related links")
        print()

        # Check if there are any bundles at all (including Active/Closed)
        from ado.client import _api_url, _auth_header, API_VERSION
        import httpx
        wiql = {
            "query": """
                SELECT [System.Id], [System.Title], [System.State]
                FROM WorkItems
                WHERE [System.WorkItemType] = 'Task'
                  AND [System.Tags] CONTAINS 'RegressionBundle'
                ORDER BY [System.CreatedDate] DESC
            """
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                _api_url("wit/wiql"), headers=_auth_header(), json=wiql,
                params={"api-version": API_VERSION},
            )
            resp.raise_for_status()
        all_ids = [item["id"] for item in resp.json().get("workItems", [])]
        if all_ids:
            all_items = await get_work_items_batch(all_ids)
            print(f"  All RegressionBundle Tasks (any state): {len(all_items)}")
            for item in all_items:
                f = item.get("fields", {})
                print(f"    [{item['id']}] {f.get('System.Title', '?')}  State={f.get('System.State', '?')}  Tags={f.get('System.Tags', '?')}")
            print()
            print("  TIP: To make a bundle 'pending' again, change its State to 'New' in ADO")
            print("       or create a new one from the dashboard.")
            print()

            # Use the most recent bundle for remaining tests
            latest = all_items[0]
            print(f"  Using bundle [{latest['id']}] for remaining tests (even though not New)")
        else:
            print("  No RegressionBundle Tasks found at all in ADO.")
            return
    else:
        latest = bundles[0]

    bundle_id = latest["id"]
    fields = latest.get("fields", {})
    print()

    # ── Test 2: Build the bundle_data payload (what PollerWorkflow sends to BundleProcessor) ──

    section("Build bundle_data (PollerWorkflow -> BundleProcessorWorkflow)", 2)

    import re
    infra = await get_source_infra_from_bundle(latest)
    infra_name = infra.get("fields", {}).get("System.Title", "Unknown") if infra else "Unknown"
    desc_raw = fields.get("System.Description", "")
    patch_desc = re.sub(r"<[^>]+>", "", desc_raw).strip() if desc_raw else ""

    assigned = fields.get("System.AssignedTo", "")
    if isinstance(assigned, dict):
        accountable = assigned.get("displayName", "")
    else:
        accountable = str(assigned)

    bundle_data = {
        "bundleId": str(bundle_id),
        "bundleWorkItemId": bundle_id,
        "sourceInfraName": infra_name,
        "patchDescription": patch_desc,
        "accountableParty": accountable,
    }

    dump("bundle_data payload", bundle_data, max_len=1000)
    print()

    # Validate
    issues = []
    if not bundle_data["sourceInfraName"] or bundle_data["sourceInfraName"] == "Unknown":
        issues.append("sourceInfraName is 'Unknown' - bundle may not be linked to an Epic")
    if not bundle_data["patchDescription"]:
        issues.append("patchDescription is empty - System.Description has no content")

    if issues:
        print("  [WARNINGS]:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print("  [OK] bundle_data looks correct")

    # ── Test 3: fetch_bundle_test_cases ───────────────────────────

    section("get_linked_test_cases() -> extract_test_payload()", 3)
    print(f"  Fetching test cases linked to bundle [{bundle_id}]...")
    print()

    test_cases = await get_linked_test_cases(bundle_id)
    print(f"  Found: {len(test_cases)} linked test case(s)")
    print()

    if not test_cases:
        print("  [!] No test cases linked to this bundle.")
        print("      Make sure the bundle has Related links to Test Case work items.")
        return

    # Build payloads like the activity does
    payloads = []
    for tc in test_cases:
        tc_id = tc.get("id")
        app_url = await get_app_url_for_test_case(tc)
        payload = extract_test_payload(tc, str(bundle_id))
        if app_url:
            payload["appUrl"] = app_url
        payload["_adoWorkItemId"] = tc_id
        payloads.append(payload)

    print("  PAYLOADS (what gets sent to Playwright):")
    print()
    for i, p in enumerate(payloads):
        print(f"  --- Test Case {i+1}/{len(payloads)} ---")
        print(f"    testCaseId:     {p.get('testCaseId')}")
        print(f"    testCaseName:   {p.get('testCaseName', '?')}")
        print(f"    bundleId:       {p.get('bundleId')}")
        print(f"    appUrl:         {p.get('appUrl', '[MISSING]')}")
        print(f"    appName:        {p.get('appName', '[MISSING]')}")
        print(f"    _adoWorkItemId: {p.get('_adoWorkItemId')}")
        steps = p.get("steps", [])
        print(f"    steps:          {len(steps)} step(s)")
        for s in steps[:3]:
            print(f"      Step {s.get('stepNumber')}: {s.get('action', '?')[:60]}")
            print(f"        Expected: {s.get('expectedResult', '?')[:60]}")
        if len(steps) > 3:
            print(f"      ... and {len(steps) - 3} more step(s)")
        print()

    # Validate
    issues = []
    for p in payloads:
        if not p.get("appUrl"):
            issues.append(f"TC [{p.get('_adoWorkItemId')}] has no appUrl - Playwright needs this!")
        if not p.get("steps") or len(p["steps"]) == 0:
            issues.append(f"TC [{p.get('_adoWorkItemId')}] has no steps - Playwright needs steps!")

    if issues:
        print("  [WARNINGS]:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print("  [OK] All payloads have appUrl and steps")

    # ── Test 4: LangGraph payload ─────────────────────────────────

    section("LangGraph analysis payload (what BundleProcessor sends to LangGraph)", 4)

    # Simulate Playwright results
    simulated_results = []
    for p in payloads:
        simulated_results.append({
            "bundleId": p.get("bundleId"),
            "testCaseId": p.get("testCaseId"),
            "appName": p.get("appName", "Unknown App"),
            "overallResult": "PASS",
            "executionTime": "10s",
            "steps": [
                {
                    "stepNumber": s.get("stepNumber"),
                    "result": "PASS",
                    "actual": s.get("expectedResult", "Verified"),
                    "screenshot": "[base64 data]",
                }
                for s in p.get("steps", [])
            ],
        })

    analysis_payload = {
        "bundleId": str(bundle_id),
        "infrastructureComponent": infra_name,
        "patchDescription": patch_desc,
        "testResults": simulated_results,
    }

    dump("analysis_payload (to LangGraph)", analysis_payload, max_len=2000)
    print()
    print(f"  Total test results: {len(simulated_results)}")
    print(f"  (These are simulated — real results come from Playwright)")

    # ── Summary ───────────────────────────────────────────────────

    print()
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print()
    print(f"  Bundle ID:          {bundle_id}")
    print(f"  Bundle State:       {fields.get('System.State', '?')}")
    print(f"  Source Infra:       {infra_name}")
    print(f"  Patch Description:  {patch_desc[:60] or '[empty]'}")
    print(f"  Accountable Party:  {accountable or '[empty]'}")
    print(f"  Linked Test Cases:  {len(test_cases)}")
    print(f"  Total Steps:        {sum(len(p.get('steps', [])) for p in payloads)}")
    missing_urls = sum(1 for p in payloads if not p.get("appUrl"))
    missing_steps = sum(1 for p in payloads if not p.get("steps"))
    if missing_urls:
        print(f"  [!] {missing_urls} test case(s) missing appUrl")
    if missing_steps:
        print(f"  [!] {missing_steps} test case(s) missing steps")
    if not missing_urls and not missing_steps:
        print(f"  Status:             READY FOR PIPELINE")
    print()


if __name__ == "__main__":
    asyncio.run(main())
