# Customer Support AgentOS

A working multi-agent customer-support portfolio built on **AgentOS** and **Agno**. It shows how a public Customer Support team can route a customer conversation to private specialists, keep an approval-gated refund read-only for the operator, and present a deterministic demo without inventing activity or spending model calls.

**For recruiters and engineering reviewers:** start with the local Support Inbox. The three seeded conversations make the routing, product help, and approval boundary visible immediately. This repository also retains the AgentOS platform surfaces behind the showcase: Studio, MCP, coding-agent workflows, observability, and production deployment.

> **Built on AgentOS / Agno.** AgentOS provides the runtime, governance, sessions, tracing, MCP server, and Studio; [Agno](https://docs.agno.com) provides the agent framework. This portfolio implements the Customer Support experience on that foundation.

## Recruiter quick path

1. Start the deterministic local demo:

   ```sh
   docker compose up -d --build agentos-api support-inbox-db support-inbox-migrate support-inbox-bff
   ```

2. Open [Support Inbox](http://localhost:8000/support-inbox), sign in with the local-only account, and review the three seeded threads.
3. Show the three outcomes: **Order Support** resolves tracking, **Product Support** answers sizing, and **Returns & Refunds Support** leaves a refund as **Awaiting administrative review**.

The default local-only credentials are `local.operator` / `local-support-password`. Override `SUPPORT_OPERATOR_USERNAME`, `SUPPORT_OPERATOR_PASSWORD`, and `SUPPORT_OPERATOR_DISPLAY_NAME` for local development; never use the defaults outside local development.

For the exact walkthrough and honest capture guidance, see [the recruiter demo guide](docs/recruiter-demo.md).

## What this portfolio demonstrates

| Outcome | Evidence in the demo |
| --- | --- |
| Customer requests reach the right expertise | The public Customer Support team routes order, product, and return/refund work to private specialists. |
| The customer-facing surface stays bounded | Support Inbox can compose, reply, refresh, and retry; it does not expose internal runs or administrative controls. |
| Approval is visible but not delegated | A refund can show **Awaiting administrative review**. Support Inbox cannot approve, reject, resume, or administer that request. |
| The portfolio is reproducible | Startup seeds three fixed synthetic threads without model, tool, or knowledge-base calls. |

## Architecture at a glance

- **Public Customer Support team:** the customer-facing team receives the conversation and selects the appropriate specialist.
- **Private specialists:** **Order Support**, **Product Support**, and **Returns & Refunds Support** hold their focused support responsibilities behind the team.
- **Support Inbox and BFF boundary:** the local React inbox talks to its dedicated BFF, which exposes only the customer-safe inbox operations. It is not an administrative console.
- **Deterministic seed:** three typed synthetic inbox threads are created when missing, giving a repeatable review path before anyone submits a live email.
- **Separate Support Insights:** **Support Insights** is an administrator-only validation surface. It is deliberately separate from Support Inbox and is not part of the customer-facing demo.

## The deterministic Support Inbox demo

The local Support Inbox is a React/Vite frontend for reviewing `customer-support` conversations and sending simulated customer emails through the existing AgentOS API.

### Seeded states to review

1. **Tracking update** — a completed order-status response, routed through **Order Support**.
2. **Mosslight Tee sizing** — a completed product-sizing response, routed through **Product Support**.
3. **Refund review** — a paused simulated refund request, routed through **Returns & Refunds Support** and displayed as **Awaiting administrative review**.

These are the only seeded states. They are static records: the seed creates missing fixed sessions but never replaces, merges, or mutates an existing demo thread. Submitting a new email is the optional interactive path and may invoke the configured model and specialist tools.

### Run the local Compose stack

From the repository root:

```sh
docker compose up -d --build agentos-api support-inbox-db support-inbox-migrate support-inbox-bff
```

Compose waits for PostgreSQL, applies the Support Inbox migrations, seeds one local-only operator, and starts the BFF at [http://localhost:8001](http://localhost:8001). The deterministic inbox threads are seeded during AgentOS startup.

### Frontend development and build

For Vite development:

```sh
cd frontend/support-inbox
npm ci
npm exec vite -- --host 127.0.0.1 --port 5173
```

This serves the SPA at [http://localhost:5173/support-inbox/](http://localhost:5173/support-inbox/). The Vite configuration has no development proxy for `/api/support/*`; use the FastAPI-served build for end-to-end inbox requests.

To generate the static assets served by FastAPI:

```sh
cd frontend/support-inbox
npm ci
VITE_SUPPORT_API_ORIGIN=http://localhost:8001 npm run build
```

`VITE_SUPPORT_API_ORIGIN` is a build-time variable. Always include it when rebuilding `dist/`; otherwise the bundle has no BFF URL and reports that the support service is unavailable. The build uses `/support-inbox/`; with Compose running, [http://localhost:8000/support-inbox](http://localhost:8000/support-inbox) redirects to the served build. Hard-refresh after rebuilding to discard the prior bundle.

## Platform capabilities

Customer Support is the project outcome. The following AgentOS capabilities are the supporting platform for operating, extending, and deploying it.

### Local platform onboarding

> **Prerequisite:** [Docker](https://www.docker.com/get-started/) installed and running.

If you are viewing or have cloned this repository, configure and run it from its root:

```sh
cp example.env .env
# Open .env and set OPENAI_API_KEY
docker compose up -d --build
```

Confirm the API at [http://localhost:8000/docs](http://localhost:8000/docs).

### AgentOS UI

1. Open [os.agno.com](https://os.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agentos-railway&utm_content=agentos-railway&utm_term=railway) and sign in.
2. Click **Connect OS**, enter `http://localhost:8000`, name it **Local AgentOS**, and connect.
3. Use **Agno** to reach the platform agents: Platform Builder builds runtime components, Platform Manager reads platform health, and Platform Engineer explains repository wiring.

### Studio and coding-agent workflows

AgentOS supports three complementary ways to create agents, teams, and workflows:

1. **Coding agents:** the skills in [`.agents/skills/`](.agents/skills/) guide creation, extension, evaluation, review, and deployment.
2. **Natural language:** Platform Builder creates runtime components through the governed Studio registry.
3. **No-code Studio:** build and inspect components visually in AgentOS Studio.

To add an agent with a coding agent, run `/create-agent`. To make a bounded change, use `/extend-agent`; `/improve-agent` hardens an existing agent; `/create-evals` authors coverage; `/eval-and-improve` diagnoses failing cases; and `/review-and-improve` checks documentation and configuration drift.

Run evals from a host venv:

```sh
./scripts/venv_setup.sh && source .venv/bin/activate
python -m evals --tag smoke
python -m evals --tag release
python -m evals --name <case>
```

The daily run-evals schedule ships disabled because it incurs model calls. Enable it from the AgentOS UI only when that recurring cost and its shared-store implications are appropriate.

### Inspect Customer Support approval-gated runs

Support Inbox intentionally cannot administer approvals. An authorized administrator can inspect a paused Customer Support team run before resuming it. Replace `THREAD-REFUND-1004` and `<RUN_ID>` with the relevant values:

```bash
curl -sS \
  "http://localhost:8000/teams/customer-support/runs?session_id=THREAD-REFUND-1004" \
  | jq

curl -sS \
  "http://localhost:8000/teams/customer-support/runs/<RUN_ID>?session_id=THREAD-REFUND-1004" \
  | jq
```

If the session ID is unknown, list recent Customer Support team sessions:

```bash
curl -sS \
  "http://localhost:8000/sessions?type=team&component_id=customer-support&limit=20" \
  | jq
```

### MCP and other clients

AgentOS exposes an MCP server at `/mcp`, enabled by `mcp_server=True` in [`app/main.py`](app/main.py). MCP clients can call agents, teams, and workflows through tools such as `run_agent`, `run_team`, and `run_workflow`.

Register local MCP clients:

```sh
uvx agno connect
```

It detects Claude Code, Claude Desktop, Codex, and Cursor and registers `http://localhost:8000/mcp`. For claude.ai and ChatGPT (web), deploy first, add `https://<domain>/mcp` as a connector, and approve the OAuth consent page with the deployment's `MCP_CONNECT_SECRET`.

## Production deployment on Railway

The repository includes Railway deployment scripts and the [`/deploy-platform`](.agents/skills/deploy-platform/SKILL.md) skill. You can deploy to any container platform; these instructions cover Railway.

> **Prerequisite:** [Railway CLI](https://docs.railway.com/cli#installing-the-cli) installed and `railway login` completed.

### 1. Set production environment values

```sh
cp .env .env.production          # or cp example.env .env.production
# Edit .env.production with production values
```

Keep production credentials separate from local credentials.

### 2. Deploy and configure authentication

```sh
./scripts/railway/up.sh
```

The script provisions the AgentOS service and Postgres on a private network, creates a domain, and asks for JWT verification material. In [os.agno.com](https://os.agno.com), connect the Railway domain as **Live AgentOS**, enable **Token-Based Authorization (JWT)**, copy the public key, and paste it into the prompt. Production refuses to serve traffic without `JWT_VERIFICATION_KEY` or `JWT_JWKS_FILE`.

Token-based authorization supplies no-public-access protection, per-request identity, and scope-based permissions. Do not disable it unless the service is inside a private VPC behind another authentication layer.

For web MCP clients, use `https://<railway-domain>/mcp` as the connector URL and enter the `MCP_CONNECT_SECRET` generated by `up.sh`. For desktop coding clients:

```sh
uvx agno connect --url https://<railway-domain>
```

### 3. Operate the deployment

```sh
railway logs --service agent-os
./scripts/railway/redeploy.sh
./scripts/railway/env-sync.sh
```

`./scripts/railway/down.sh` deletes the Railway project, including its database and volume. Treat it as destructive.

## Security and environment reference

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | yes | none | OpenAI key for models and embeddings. |
| `RUNTIME_ENV` | no | `prd` | `dev` disables JWT. Never sync `dev` into production. |
| `JWT_VERIFICATION_KEY` / `JWT_JWKS_FILE` | prd | none | Production JWT verification material. |
| `AGENTOS_URL` | no | `http://127.0.0.1:8000` | Scheduler base URL and OAuth public-origin input. |
| `MCP_CONNECT_SECRET` | no | none | Enables MCP OAuth for claude.ai and ChatGPT; requires `AGENTOS_URL`. |
| `AGENTOS_MCP_SIGNING_KEY` | no | none | Optional high-entropy OAuth token signing material. |
| `ENABLE_DEPLOY_CHECK` | no | `True` | Owns the daily deployment-check schedule toggle. |
| `EVALS_TAG` | no | `smoke` | Eval tag selected by the run-evals workflow. |
| `EVALS_CASE_TIMEOUT_SECONDS` / `EVALS_SUITE_TIMEOUT_SECONDS` | no | `90` / derived | Eval timeout controls. |
| `PARALLEL_API_KEY` | no | none | Enables authenticated web search. |
| `SLACK_BOT_TOKEN` / `SLACK_SIGNING_SECRET` | no | none | Both enable Slack; the token also enables the registry's send-only Slack toolkit. |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASS` / `DB_DATABASE` | no | compose defaults | PostgreSQL connection settings. |
| `DB_DRIVER` | no | `postgresql+psycopg` | SQLAlchemy driver. |
| `AGNO_DEBUG` / `WAIT_FOR_DB` | no | `False` | Debug logging and startup DB wait controls. |
| `SUPPORT_DB_USER` / `SUPPORT_DB_PASSWORD` / `SUPPORT_DB_NAME` | deployment | compose local defaults | Separate Support Inbox PostgreSQL credentials and database name. |
| `SUPPORT_OPERATOR_USERNAME` / `SUPPORT_OPERATOR_PASSWORD` / `SUPPORT_OPERATOR_DISPLAY_NAME` | deployment | compose local defaults | Separate Support Inbox operator seed identity; override outside local Compose. |
| `DATABASE_URL` / `AGENTOS_BASE_URL` / `AGENTOS_PAT` | deployment | compose local wiring | BFF database connection, AgentOS service URL, and service-account token; set deployment-specific values. |
| `SUPPORT_ALLOWED_ORIGINS` / `SUPPORT_COOKIE_SECURE` / `SUPPORT_COOKIE_NAME` | deployment | compose local wiring | BFF browser-origin and session-cookie boundary; use deployment-specific secure settings. |

Support Inbox uses this separate BFF/operator/database boundary; these variables do not configure the Customer Support AgentOS team itself. Compose supplies local-only wiring, while deployments must provide their own values without copying local defaults.

Keep secrets out of source control. `MCP_CONNECT_SECRET` must be at least 16 characters; `AGENTOS_MCP_SIGNING_KEY` must be high entropy and at least 32 characters. In production, service-account and JWT scopes should grant only the operations a caller needs.

## Learn more

- [Agno documentation](https://docs.agno.com)
- [AgentOS introduction](https://docs.agno.com/agent-os/introduction)
- [Agno on GitHub](https://github.com/agno-agi/agno)
