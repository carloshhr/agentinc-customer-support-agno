# Customer Support AgentOS recruiter demo

This local portfolio demo shows the public **Customer Support AgentOS** experience through Support Inbox. It seeds synthetic, typed inbox threads during AgentOS startup; the seed does not call a model, tools, or the product knowledge base.

Support Inbox is a customer-safe surface, not an administration console. **Support Insights** remains separate as an operator-facing reporting and validation surface.

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

## Seeded states to show

The inbox shows exactly these three deterministic conversations immediately after startup:

1. **Tracking update** — a completed order-status response from **Order Support**.
2. **Mosslight Tee sizing** — a completed product-sizing response from **Product Support**, with a typed support category and issue code.
3. **Refund review** — a paused simulated refund request from **Returns & Refunds Support**, displayed as **Awaiting administrative review** without exposing approval internals.

The seed only creates missing fixed demo sessions. It never replaces, merges, or mutates an existing demo thread.

## What to explain

- The public Customer Support team routes each request to a private specialist.
- Support Inbox supports compose, reply, manual refresh, and retry for simulated customer conversations.
- The refund state is intentionally read-only: Support Inbox cannot approve, reject, resume, or otherwise administer a request.
- **Support Insights** is a distinct operator-facing reporting and validation surface and is not part of this inbox walkthrough.

## Capture portfolio visuals

Capture real screenshots or a short GIF only from the three seeded states above: Tracking update, Mosslight Tee sizing, and Refund review. Start from a clean local demo, capture each state as it appears, and label the refund state as **Awaiting administrative review**. Do not imply that the seeded records are live customer traffic, and do not use Support Insights or administrative controls in the capture.

## Model usage

The seeded threads are static demo records. Submitting a new simulated customer email is different: Customer Support may invoke the configured model and, depending on the request, its specialist tools. Keep an OpenAI API key configured only when you want to exercise that interactive path.
