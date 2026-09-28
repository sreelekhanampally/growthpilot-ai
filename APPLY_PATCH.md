# GrowthPilot v1.1 multi-agent integration

This patch integrates the reusable ContextOps orchestration patterns into GrowthPilot:

- supervisor routing;
- analytics, Customer 360, retrieval, and hybrid specialists;
- Gemini/Ollama provider support and failover;
- deterministic no-key fallback;
- grounding validation and one repair pass;
- citations, workflow traces, confidence, and provider display in React.

It deliberately does not copy ContextOps ticket/incident tables or unrestricted text-to-SQL.
GrowthPilot agents can call only approved customer-intelligence functions.

## Apply to an existing GrowthPilot folder

1. Stop backend and frontend using `Ctrl+C`.
2. Extract this ZIP over the root of `growthpilot-ai`.
3. Select **Replace the files in the destination**.
4. Run:

```powershell
cd C:\path\to\growthpilot-ai
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
$env:DATABASE_URL = "sqlite+pysqlite:///growthpilot.db"
python -m pytest
python -m growthpilot serve
```

5. In another terminal:

```powershell
cd C:\path\to\growthpilot-ai\frontend
npm install
npm run dev
```

No database migration, data reload, feature rebuild, or model retraining is required.

## Enable Gemini

Create `.env` in the project root:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=replace_with_your_key
GEMINI_MODEL=gemini-2.5-flash
```

Restart the backend. Never commit `.env`.

## Enable local Ollama

```env
LLM_PROVIDER=ollama
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
```

See `docs/MULTI_AGENT_COPILOT.md` for the full architecture and hybrid configuration.
