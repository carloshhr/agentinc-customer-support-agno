# Local Recruiter Demo

The local Customer Support demo seeds synthetic, typed inbox threads during AgentOS startup. It does not call a model, tools, or the product knowledge base to create those threads.

## Start the demo

```sh
cp example.env .env
# Set OPENAI_API_KEY before submitting new emails.
docker compose up -d --build
```

Open:

- Support Inbox: <http://localhost:8000/support-inbox/>
- API documentation: <http://localhost:8000/docs>
- BFF health check: <http://localhost:8001/health>

Use the local-only operator account:

```text
Username: local.operator
Password: local-support-password
```

Do not use these credentials outside local development.

## Seeded scenarios

The inbox shows these conversations immediately after startup:

1. **Tracking update** — a completed order-status response grounded in the seeded order fixture.
2. **Mosslight Tee sizing** — a completed product-sizing response with a typed support category and issue code.
3. **Refund review** — a paused simulated refund request that demonstrates the approval-pending state without exposing approval internals.

The seed only creates missing fixed demo sessions. It never replaces, merges, or mutates an existing demo thread.

## Model usage

The seeded threads are static demo records. Submitting a new simulated customer email is different: Customer Support may invoke the configured model and, depending on the request, its specialist tools. Keep an OpenAI API key configured only when you want to exercise that interactive path.
