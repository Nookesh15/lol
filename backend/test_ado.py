"""
ADO Client Test Script — Test against real ADO using standard fields.

Usage: python test_ado.py
"""

import asyncio
import sys
import os
import io
import json
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

import httpx
import base64

ADO_ORG_URL = os.getenv("ADO_ORG_URL", "").rstrip("/")
ADO_PROJECT = os.getenv("ADO_PROJECT", "")
ADO_PAT = os.getenv("ADO_PAT", "")
API_VERSION = "7.1"

WIT_INFRA = os.getenv("ADO_WIT_INFRA", "Epic")
WIT_APP = os.getenv("ADO_WIT_APP", "Feature")
WIT_TESTCASE = os.getenv("ADO_WIT_TESTCASE", "Test Case")
WIT_BUNDLE = os.getenv("ADO_WIT_BUNDLE", "Task")


def _auth_header():
    encoded = base64.b64encode(f":{ADO_PAT}".encode()).decode()
    return {"Authorization": f"Basic {encoded}", "Content-Type": "application/json"}


def _api_url(path):
    return f"{ADO_ORG_URL}/{ADO_PROJECT}/_apis/{path}"


async def test_1_config():
    print("=" * 60)
    print("  TEST 1: Configuration")
    print("=" * 60)
    print(f"\n  ADO_ORG_URL: {ADO_ORG_URL or '(not set)'}")
    print(f"  ADO_PROJECT: {ADO_PROJECT or '(not set)'}")
    print(f"  ADO_PAT:     {'***' + ADO_PAT[-4:] if len(ADO_PAT) > 4 else '(not set)'}")
    print(f"  Types:       Infra={WIT_INFRA}, App={WIT_APP}, TC={WIT_TESTCASE}, Bundle={WIT_BUNDLE}")

    if not all([ADO_ORG_URL, ADO_PROJECT, ADO_PAT]):
        print("\n  [FAIL] Missing credentials. Edit backend/.env")
        return False
    print("\n  [PASS]")
    return True


async def test_2_connection():
    print("\n" + "=" * 60)
    print("  TEST 2: ADO Connection")
    print("=" * 60)
    url = f"{ADO_ORG_URL}/_apis/projects/{ADO_PROJECT}?api-version={API_VERSION}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=_auth_header())
        if resp.status_code == 200:
            print(f"  Project: {resp.json().get('name')}")
            print("  [PASS]")
            return True
        print(f"  [FAIL] HTTP {resp.status_code}")
        return False
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


async def test_3_infra_components():
    """Query Infrastructure Components (Epics)."""
    print("\n" + "=" * 60)
    print(f"  TEST 3: Infrastructure Components ({WIT_INFRA})")
    print("=" * 60)
    wiql = {"query": f"SELECT [System.Id] FROM WorkItems WHERE [System.WorkItemType] = '{WIT_INFRA}' ORDER BY [System.CreatedDate] DESC"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_api_url("wit/wiql"), headers=_auth_header(), json=wiql, params={"api-version": API_VERSION})
            resp.raise_for_status()
        ids = [i["id"] for i in resp.json().get("workItems", [])]
        print(f"  Found: {len(ids)}")

        if ids:
            async with httpx.AsyncClient(timeout=10.0) as client:
                dr = await client.get(_api_url("wit/workitems"), headers=_auth_header(),
                    params={"ids": ",".join(str(i) for i in ids[:10]), "$expand": "relations", "api-version": API_VERSION})
                dr.raise_for_status()
            for wi in dr.json().get("value", []):
                f = wi.get("fields", {})
                rels = len(wi.get("relations", []) or [])
                print(f"    [{wi['id']}] {f.get('System.Title')} (State: {f.get('System.State')}, Links: {rels})")
        print("  [PASS]")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


async def test_4_applications():
    """Query Applications (Features) and check for URLs in Description."""
    print("\n" + "=" * 60)
    print(f"  TEST 4: Applications ({WIT_APP})")
    print("=" * 60)
    wiql = {"query": f"SELECT [System.Id] FROM WorkItems WHERE [System.WorkItemType] = '{WIT_APP}' ORDER BY [System.CreatedDate] DESC"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_api_url("wit/wiql"), headers=_auth_header(), json=wiql, params={"api-version": API_VERSION})
            resp.raise_for_status()
        ids = [i["id"] for i in resp.json().get("workItems", [])]
        print(f"  Found: {len(ids)}")

        if ids:
            async with httpx.AsyncClient(timeout=10.0) as client:
                dr = await client.get(_api_url("wit/workitems"), headers=_auth_header(),
                    params={"ids": ",".join(str(i) for i in ids[:10]), "$expand": "relations", "api-version": API_VERSION})
                dr.raise_for_status()
            for wi in dr.json().get("value", []):
                f = wi.get("fields", {})
                desc = f.get("System.Description", "") or ""
                # Try to find a URL
                url_match = re.search(r'https?://[^\s<"\']+', desc)
                app_url = url_match.group(0) if url_match else "(no URL in Description)"
                rels = len(wi.get("relations", []) or [])
                print(f"    [{wi['id']}] {f.get('System.Title')} (Links: {rels})")
                print(f"           URL: {app_url}")
        print("  [PASS]")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


async def test_5_test_cases():
    """Query Test Cases and check for steps."""
    print("\n" + "=" * 60)
    print(f"  TEST 5: Test Cases ({WIT_TESTCASE})")
    print("=" * 60)
    wiql = {"query": f"SELECT [System.Id] FROM WorkItems WHERE [System.WorkItemType] = '{WIT_TESTCASE}' ORDER BY [System.CreatedDate] DESC"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_api_url("wit/wiql"), headers=_auth_header(), json=wiql, params={"api-version": API_VERSION, "$top": "10"})
            resp.raise_for_status()
        ids = [i["id"] for i in resp.json().get("workItems", [])]
        print(f"  Found: {len(ids)}")

        if ids:
            async with httpx.AsyncClient(timeout=10.0) as client:
                dr = await client.get(_api_url("wit/workitems"), headers=_auth_header(),
                    params={"ids": ",".join(str(i) for i in ids[:10]), "$expand": "relations", "api-version": API_VERSION})
                dr.raise_for_status()
            from ado.client import parse_test_steps
            for wi in dr.json().get("value", []):
                f = wi.get("fields", {})
                steps = parse_test_steps(wi)
                tags = f.get("System.Tags", "") or ""
                rels = len(wi.get("relations", []) or [])
                print(f"    [{wi['id']}] {f.get('System.Title')}")
                print(f"           State: {f.get('System.State')}, Links: {rels}, Tags: {tags or '(none)'}")
                print(f"           Steps: {len(steps)} found")
                if steps:
                    for s in steps[:3]:
                        print(f"             Step {s['stepNumber']}: {s['action'][:50]}...")
                # Check for TCM steps field
                tcm = f.get("Microsoft.VSTS.TCM.Steps", "")
                if tcm:
                    print(f"           TCM Steps: {len(tcm)} chars (XML)")
                else:
                    print(f"           TCM Steps: (empty - add steps in ADO Test Case editor)")
        print("  [PASS]")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


async def test_6_pending_bundles():
    """Test querying pending bundles via ado.client."""
    print("\n" + "=" * 60)
    print("  TEST 6: Pending Bundles (via ado.client)")
    print("=" * 60)
    try:
        from ado.client import query_pending_bundles
        bundles = await query_pending_bundles()
        print(f"  Pending bundles: {len(bundles)}")
        for b in bundles:
            f = b.get("fields", {})
            print(f"    [{b['id']}] {f.get('System.Title')} (State: {f.get('System.State')}, Tags: {f.get('System.Tags', '')})")
        print("  [PASS]")
        return True
    except Exception as e:
        print(f"  Result: {e}")
        print("  (Expected if no Task tagged 'RegressionBundle' exists with State=New)")
        print("  [INFO] To create a test bundle, use test_ado.py create_bundle")
        return "WARN"


async def test_7_link_traversal():
    """Test the full link chain: Infra (Epic) -> App (Feature) -> Test Case."""
    print("\n" + "=" * 60)
    print("  TEST 7: Link Traversal (Infra -> App -> Test Case)")
    print("=" * 60)
    # Find an Infra component with links
    wiql = {"query": f"SELECT [System.Id] FROM WorkItems WHERE [System.WorkItemType] = '{WIT_INFRA}' ORDER BY [System.CreatedDate] DESC"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_api_url("wit/wiql"), headers=_auth_header(), json=wiql, params={"api-version": API_VERSION})
            resp.raise_for_status()
        ids = [i["id"] for i in resp.json().get("workItems", [])]
        if not ids:
            print("  No infrastructure items found")
            return "SKIP"

        # Get with relations
        async with httpx.AsyncClient(timeout=10.0) as client:
            dr = await client.get(_api_url("wit/workitems"), headers=_auth_header(),
                params={"ids": ",".join(str(i) for i in ids[:5]), "$expand": "relations", "api-version": API_VERSION})
            dr.raise_for_status()

        for infra in dr.json().get("value", []):
            title = infra.get("fields", {}).get("System.Title", "?")
            rels = infra.get("relations", []) or []
            if not rels:
                print(f"  [{infra['id']}] {title} - no links (skip)")
                continue

            print(f"\n  [{infra['id']}] {title}")
            for rel in rels:
                rel_type = rel.get("rel", "")
                url = rel.get("url", "")
                try:
                    child_id = int(url.rstrip("/").split("/")[-1])
                except:
                    continue
                items = await httpx.AsyncClient(timeout=10.0).__aenter__()
                # Fetch the linked item
                from ado.client import get_work_items_batch
                children = await get_work_items_batch([child_id])
                for c in children:
                    cf = c.get("fields", {})
                    ctype = cf.get("System.WorkItemType", "?")
                    ctitle = cf.get("System.Title", "?")
                    print(f"    -> [{c['id']}] ({ctype}) {ctitle} (rel: {rel_type.split('.')[-1]})")

        print("\n  [PASS]")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


async def main():
    print("\n" + "*" * 60)
    print("  LOL Backend -- ADO Client Test (Standard Fields)")
    print("*" * 60)

    if not await test_1_config():
        return
    if not await test_2_connection():
        return

    await test_3_infra_components()
    await test_4_applications()
    await test_5_test_cases()
    await test_6_pending_bundles()
    await test_7_link_traversal()

    print("\n" + "=" * 60)
    print("  DONE")
    print("=" * 60)
    print("\n  Field Mapping (Standard ADO Fields):")
    print("    Bundle Status     -> System.State (New/Active/Closed)")
    print("    Regression Flag   -> System.Tags  (RegressionFlag:value)")
    print("    Test Result       -> System.Tags  (TestResult:PASS/FAIL)")
    print("    Patch Description -> System.Description")
    print("    Error Details     -> System.History (comment)")
    print("    App URL           -> System.Description (URL in text)")
    print("    Bundle identifier -> System.Tags  (RegressionBundle)")


if __name__ == "__main__":
    asyncio.run(main())
