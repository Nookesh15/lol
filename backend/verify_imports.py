"""Quick import verification."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, ".")

ok = 0
fail = 0

modules = [
    ("ado.client", "query_pending_bundles, get_linked_test_cases"),
    ("temporal_app.activities.ado_activities", "poll_pending_bundles"),
    ("temporal_app.activities.playwright_dispatch", "dispatch_to_playwright"),
    ("temporal_app.activities.langgraph_invoke", "invoke_langgraph_analysis"),
    ("temporal_app.workflows.bundle_processor", "BundleProcessorWorkflow"),
    ("temporal_app.workflows.poller", "PollerWorkflow"),
    ("langgraph_agent.agent", "analyze_bundle, build_graph"),
    ("langgraph_agent.server", "app"),
]

for mod, names in modules:
    try:
        __import__(mod)
        print(f"  OK: {mod}")
        ok += 1
    except Exception as e:
        print(f"  FAIL: {mod} -> {e}")
        fail += 1

print(f"\nResult: {ok} passed, {fail} failed")
