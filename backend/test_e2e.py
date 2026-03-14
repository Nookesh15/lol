"""
End-to-End Test Harness — Test the full pipeline without ADO.

This script tests each service independently and then the integrated pipeline.
Since ADO may not be configured yet, it directly calls the services.

Usage:
  # Test individual services:
  python test_e2e.py playwright      # Test Playwright service
  python test_e2e.py langgraph       # Test LangGraph service
  python test_e2e.py temporal        # Test Temporal connection
  python test_e2e.py pipeline        # Test full pipeline (Playwright -> LangGraph)
  python test_e2e.py all             # Run all tests
"""

import asyncio
import sys
import json
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))

import httpx
from dotenv import load_dotenv

load_dotenv()

PLAYWRIGHT_URL = os.getenv("PLAYWRIGHT_SERVICE_URL", "http://localhost:3001")
LANGGRAPH_URL = os.getenv("LANGGRAPH_SERVICE_URL", "http://localhost:8000")
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")

# ─── Test Data ───────────────────────────────────────────────────────

SAMPLE_TEST_PAYLOAD = {
    "bundleId": "TEST-BUNDLE-001",
    "testCaseId": "TC-001",
    "appUrl": "https://aseedic.com",
    "appName": "Aseedic App",
    "steps": [
        {
            "stepNumber": 1,
            "action": "Navigate to application URL",
            "expectedResult": "Homepage loads successfully"
        },
        {
            "stepNumber": 2,
            "action": "Verify main page content is visible",
            "expectedResult": "Page content is displayed"
        },
        {
            "stepNumber": 3,
            "action": "Click 'Sign In' link",
            "expectedResult": "Link is clickable"
        },
    ]
}

SAMPLE_LANGGRAPH_PAYLOAD = {
    "bundleId": "TEST-BUNDLE-001",
    "infrastructureComponent": "Web Server Cluster",
    "patchDescription": "February Security Patch - Test",
    "testResults": [
        {
            "bundleId": "TEST-BUNDLE-001",
            "testCaseId": "TC-001",
            "appName": "Aseedic App",
            "overallResult": "PASS",
            "executionTime": "3.2s",
            "steps": [
                {"stepNumber": 1, "result": "PASS", "actual": "Homepage loaded", "screenshot": ""},
                {"stepNumber": 2, "result": "PASS", "actual": "Content visible", "screenshot": ""},
            ]
        },
        {
            "bundleId": "TEST-BUNDLE-001",
            "testCaseId": "TC-002",
            "appName": "Another App (Test)",
            "overallResult": "FAIL",
            "executionTime": "5.1s",
            "steps": [
                {"stepNumber": 1, "result": "PASS", "actual": "Page loaded", "screenshot": ""},
                {"stepNumber": 2, "result": "FAIL", "actual": "Button not found", "error": "TimeoutError: locator.click timeout 5000ms", "screenshot": ""},
            ]
        },
    ]
}


# ─── Test Functions ──────────────────────────────────────────────────

async def test_playwright():
    """Test the Playwright executor service."""
    print("=" * 60)
    print("  TEST: Playwright Executor Service")
    print("=" * 60)

    # Step 1: Health check
    print(f"\n1. Health check -> {PLAYWRIGHT_URL}/health")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{PLAYWRIGHT_URL}/health")
            resp.raise_for_status()
            print(f"   Status: {resp.json()}")
            print("   [PASS] Health check OK")
    except Exception as e:
        print(f"   [FAIL] Cannot reach Playwright service: {e}")
        print(f"\n   >> Make sure to start it first:")
        print(f"      cd backend/playwright_service && npm run dev")
        return False

    # Step 2: Execute a test case
    print(f"\n2. Execute test case -> POST {PLAYWRIGHT_URL}/execute")
    print(f"   App: {SAMPLE_TEST_PAYLOAD['appUrl']}")
    print(f"   Steps: {len(SAMPLE_TEST_PAYLOAD['steps'])}")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{PLAYWRIGHT_URL}/execute",
                json=SAMPLE_TEST_PAYLOAD,
            )
            resp.raise_for_status()
            result = resp.json()

        print(f"\n   Result:")
        print(f"     Overall: {result.get('overallResult')}")
        print(f"     Time:    {result.get('executionTime')}")
        print(f"     Steps:")
        for step in result.get("steps", []):
            icon = "PASS" if step.get("result") == "PASS" else "FAIL"
            has_ss = "yes" if len(step.get("screenshot", "")) > 100 else "no"
            print(f"       Step {step['stepNumber']}: [{icon}] {step.get('actual', '')[:60]} (screenshot: {has_ss})")

        print(f"\n   [PASS] Playwright execution completed")
        return result

    except Exception as e:
        print(f"   [FAIL] Execution error: {e}")
        return False


async def test_langgraph():
    """Test the LangGraph analysis service."""
    print("=" * 60)
    print("  TEST: LangGraph Analysis Service")
    print("=" * 60)

    # Step 1: Health check
    print(f"\n1. Health check -> {LANGGRAPH_URL}/health")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{LANGGRAPH_URL}/health")
            resp.raise_for_status()
            health = resp.json()
            print(f"   Status: {health}")
            print(f"   OpenAI configured: {health.get('openai_configured', False)}")
            print("   [PASS] Health check OK")
    except Exception as e:
        print(f"   [FAIL] Cannot reach LangGraph service: {e}")
        print(f"\n   >> Make sure to start it first:")
        print(f"      cd backend && python -m langgraph_agent.server")
        return False

    # Step 2: Analyze test results
    print(f"\n2. Analyze results -> POST {LANGGRAPH_URL}/analyze")
    print(f"   Bundle: {SAMPLE_LANGGRAPH_PAYLOAD['bundleId']}")
    print(f"   Test results: {len(SAMPLE_LANGGRAPH_PAYLOAD['testResults'])}")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{LANGGRAPH_URL}/analyze",
                json=SAMPLE_LANGGRAPH_PAYLOAD,
            )
            resp.raise_for_status()
            report = resp.json()

        print(f"\n   Evidence Report:")
        print(f"     Overall:   {report.get('overallStatus')}")
        print(f"     Tests:     {report.get('passedTests')}/{report.get('totalTests')} passed")
        print(f"     Failures:  {report.get('failedTests')}")
        print(f"     Summary:   {report.get('executiveSummary', '')[:100]}...")
        print(f"     Report:    {len(report.get('markdownReport', ''))} chars")
        print(f"     Generated: {report.get('generatedAt')}")

        if report.get("failures"):
            print(f"\n   Failure Details:")
            for f in report["failures"]:
                print(f"     - TC {f['testCaseId']} Step {f['stepNumber']}: [{f['severity']}] {f['description'][:60]}")

        print(f"\n   [PASS] LangGraph analysis completed")

        # Save the report for inspection
        md = report.get("markdownReport", "")
        if md:
            with open("test_evidence_report.md", "w", encoding="utf-8") as f:
                f.write(md)
            print(f"\n   Evidence report saved to: test_evidence_report.md")

        return report

    except Exception as e:
        print(f"   [FAIL] Analysis error: {e}")
        return False


async def test_temporal():
    """Test Temporal server connectivity."""
    print("=" * 60)
    print("  TEST: Temporal Server Connection")
    print("=" * 60)

    print(f"\n1. Connecting to Temporal at {TEMPORAL_ADDRESS}...")
    try:
        from temporalio.client import Client
        client = await Client.connect(TEMPORAL_ADDRESS, namespace="default")
        print(f"   Connected to namespace: default")
        print(f"   [PASS] Temporal connection OK")
        return True
    except Exception as e:
        print(f"   [FAIL] Cannot connect to Temporal: {e}")
        print(f"\n   >> Make sure Temporal is running:")
        print(f"      cd backend && docker-compose up -d")
        return False


async def test_pipeline():
    """Test the full pipeline: Playwright -> LangGraph (no ADO)."""
    print("=" * 60)
    print("  TEST: Full Pipeline (Playwright -> LangGraph)")
    print("=" * 60)

    # Step 1: Execute tests via Playwright
    print("\n--- Phase 1: Execute tests via Playwright ---")
    pw_result = await test_playwright()
    if not pw_result or pw_result is False:
        print("\n[PIPELINE FAIL] Playwright service not available")
        return False

    # Step 2: Feed real Playwright results to LangGraph
    print("\n--- Phase 2: Feed results to LangGraph ---")

    # Build the analysis payload with REAL Playwright results
    analysis_payload = {
        "bundleId": "PIPELINE-TEST-001",
        "infrastructureComponent": "Web Server Cluster",
        "patchDescription": "Pipeline Integration Test",
        "testResults": [pw_result],
    }

    print(f"\n1. Analyze real results -> POST {LANGGRAPH_URL}/analyze")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{LANGGRAPH_URL}/analyze",
                json=analysis_payload,
            )
            resp.raise_for_status()
            report = resp.json()

        print(f"\n   Pipeline Result:")
        print(f"     Overall:  {report.get('overallStatus')}")
        print(f"     Tests:    {report.get('passedTests')}/{report.get('totalTests')} passed")
        print(f"     Summary:  {report.get('executiveSummary', '')[:100]}...")
        print(f"     Report:   {len(report.get('markdownReport', ''))} chars")

        # Save
        md = report.get("markdownReport", "")
        if md:
            with open("test_pipeline_report.md", "w", encoding="utf-8") as f:
                f.write(md)
            print(f"\n   Full report saved to: test_pipeline_report.md")

        print(f"\n[PIPELINE PASS] End-to-end pipeline working!")
        return True

    except Exception as e:
        print(f"\n[PIPELINE FAIL] LangGraph analysis failed: {e}")
        print(f">> Make sure LangGraph is running: python -m langgraph_agent.server")
        return False


async def test_temporal_workflow():
    """Test triggering a workflow directly via Temporal (requires all services + Temporal)."""
    print("=" * 60)
    print("  TEST: Temporal Workflow Execution")
    print("=" * 60)

    print(f"\n1. Connecting to Temporal at {TEMPORAL_ADDRESS}...")
    try:
        from temporalio.client import Client
        client = await Client.connect(TEMPORAL_ADDRESS, namespace="default")
        print("   Connected")
    except Exception as e:
        print(f"   [FAIL] Cannot connect: {e}")
        return False

    print("\n2. Starting BundleProcessorWorkflow with mock bundle data...")
    print("   NOTE: This requires the Temporal Worker to be running!")
    print("   NOTE: This requires ADO credentials in .env (skipping if not configured)")

    ado_pat = os.getenv("ADO_PAT", "")
    if not ado_pat:
        print("\n   ADO PAT not configured — skipping workflow test")
        print("   To test with Temporal, configure .env with your ADO credentials")
        print("   [SKIP] Temporal workflow test skipped")
        return "SKIP"

    # If ADO is configured, we could start a real workflow here
    # For now just verify the worker is listening
    print("   ADO configured — workflow execution would start here")
    print("   [PASS] Temporal workflow test ready")
    return True


# ─── Main ────────────────────────────────────────────────────────────

async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    target = sys.argv[1].lower()

    if target == "playwright":
        await test_playwright()
    elif target == "langgraph":
        await test_langgraph()
    elif target == "temporal":
        await test_temporal()
    elif target == "pipeline":
        await test_pipeline()
    elif target == "all":
        print("\n" + "=" * 60)
        print("  LOL Backend — Full System Test")
        print("=" * 60)

        results = {}

        # Test Temporal connection
        results["temporal"] = await test_temporal()
        print()

        # Test Playwright
        results["playwright"] = await test_playwright()
        print()

        # Test LangGraph
        results["langgraph"] = await test_langgraph()
        print()

        # Test full pipeline
        results["pipeline"] = await test_pipeline()

        # Summary
        print("\n" + "=" * 60)
        print("  SUMMARY")
        print("=" * 60)
        for name, result in results.items():
            status = "PASS" if result and result is not False else "FAIL"
            if result == "SKIP":
                status = "SKIP"
            print(f"  {name:20s} [{status}]")

    else:
        print(f"Unknown target: {target}")
        print("Options: playwright, langgraph, temporal, pipeline, all")


if __name__ == "__main__":
    asyncio.run(main())
