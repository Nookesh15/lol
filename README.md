#  Automated Regression Testing — Backend

Real-time backend pipeline: polls ADO → orchestrates via Temporal → executes tests via Playwright → analyzes via LangGraph → writes evidence back to ADO.

## Architecture

```
ADO (Source of Truth)
  │
  ▼ Poll every 30s
Temporal Worker (Python)
  │
  ├──▶ Playwright Service (TypeScript, :3001)
  │     └── Runs browser tests on real apps
  │
  └──▶ LangGraph Service (Python, :8000)
        └── AI analysis + evidence report
  │
  ▼ Write results back
ADO (Updated with results, screenshots, evidence)
```

## Quick Start

### 1. Configure

```bash
cp .env.example .env
# Edit .env with your ADO credentials, Azure OpenAI keys, etc.
```

### 2. Start Temporal

```bash
docker-compose up -d
```

### 3. Start Playwright Service

```bash
cd playwright_service
npm install
npx playwright install chromium
npm run dev
# Running on http://localhost:3001
```

### 4. Start LangGraph Service

```bash
pip install -r requirements.txt
python -m langgraph_agent.server
# Running on http://localhost:8000
```

### 5. Start Temporal Worker

```bash
python -m temporal_app.worker
# Connected to Temporal, polling for work
```

### 6. Start the Poller (once)

```bash
python -c "from temporal_app.worker import start_poller; import asyncio; asyncio.run(start_poller())"
```

## How It Works

1. **UI team** flags infrastructure in ADO → creates Regression Bundle (Pending) + flags Test Cases (Needs Execution)
2. **Temporal Poller** detects Pending bundles every 30 seconds
3. **Bundle Processor Workflow** reads test cases, dispatches to Playwright, collects results
4. **Playwright** navigates real apps, executes steps, captures screenshots, returns results
5. **LangGraph** analyzes all results with Azure OpenAI, generates evidence report
6. **Temporal** writes everything back to ADO: results, screenshots, evidence, status → Complete
7. **UI team** polls ADO and displays results

## Project Structure

```
backend/
├── .env.example              # Environment variables
├── docker-compose.yml         # Temporal server
├── requirements.txt           # Python dependencies
├── ado/
│   └── client.py              # Real ADO REST API client
├── temporal_app/
│   ├── worker.py              # Entry point
│   ├── workflows/
│   │   ├── poller.py          # Polls ADO every 30s
│   │   └── bundle_processor.py # Main orchestration
│   └── activities/
│       ├── ado_activities.py  # ADO read/write
│       ├── playwright_dispatch.py
│       └── langgraph_invoke.py
├── langgraph_agent/
│   ├── agent.py               # 3-node analysis pipeline
│   ├── prompts.py             # LLM prompts
│   └── server.py              # FastAPI :8000
└── playwright_service/
    ├── package.json
    └── src/
        ├── server.ts          # Express :3001
        ├── executor.ts        # Browser test runner
        ├── step-interpreter.ts # NL → Playwright
        └── types.ts           # API types
```

## ADO Setup Requirements

Before running, create these work item types in ADO:

| Work Item Type | Key Custom Fields |
|---------------|-------------------|
| Infrastructure Component | Status, Last Patch Date, Patch Description |
| Application | AppUrl |
| Test Case | RegressionFlag, TestResult, Steps (JSON), ErrorDetails |
| Regression Bundle | Status, PatchDescription, AccountableParty, OverallResult, PassCount, FailCount |

Link structure: `Infrastructure Component → Application → Test Case → Regression Bundle`
