# Mini Agentic AI Project — Customer Support Operations Agent

This is a deliberately small project for learning the core Agentic AI pattern
without starting with a large framework.

## What the agent can do

The agent has four tools:

1. `get_order(order_id)` — inspect a simulated order-management system.
2. `get_policy(topic)` — retrieve the company's support policy.
3. `create_support_ticket(...)` — take an action that changes external state.
4. `get_ticket(ticket_id)` — verify that the action actually succeeded.

The key workflow is:

```text
User request
    ↓
LLM decides what it needs
    ↓
get_order()
    ↓
observe result
    ↓
get_policy()
    ↓
observe result
    ↓
create_support_ticket()
    ↓
observe result
    ↓
get_ticket()      ← verification
    ↓
final response
```

That is the basic agent loop:

**Goal → Reason/Decide → Act → Observe → Decide Again → Verify → Finish**

## Why this is agentic rather than a normal chatbot

A normal chatbot could simply *say* that an order should be escalated.

This agent can:

- decide which tool is necessary,
- retrieve real application state,
- use multiple tools across multiple rounds,
- change the environment by creating a ticket,
- inspect the result of its action,
- stop only after the task is resolved.

The model does **not** directly edit the JSON files. Your Python functions own
the actual side effects. This separation is important in real agent systems.

## Project structure

```text
mini_support_agent/
├── app.py
├── requirements.txt
├── .env.example
├── README.md
├── data/
│   ├── orders.json
│   ├── policies.json
│   └── tickets.json
└── tests/
    └── test_tools.py
```

## Setup

### 1. Create a virtual environment

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure the API key

Copy `.env.example` to `.env` and set:

```text
OPENAI_API_KEY=...
```

You can also change `OPENAI_MODEL`.

### 4. Run

```bash
python app.py
```

Try this first:

```text
My order ORD-1002 is late. Please investigate and help.
```

A successful run should normally involve the agent:

1. inspecting `ORD-1002`,
2. retrieving the late-delivery policy,
3. creating an escalation ticket,
4. reading the new ticket back to verify it,
5. telling you what actually happened.

## Run local tool tests

These do not call the model and can run independently of your API key:

```bash
pytest -q
```

## Things to observe while learning

Watch the terminal trace carefully. Ask yourself on every round:

- Why did the model choose this tool?
- What new observation did it receive?
- Did that observation change its next decision?
- Did it perform a side effect?
- How was that side effect verified?

Those questions are the heart of Agentic AI engineering.

## Exercises

### Exercise 1 — Add a refund-review tool

Create:

```python
request_refund_review(order_id, reason)
```

Do not let the model directly refund money. Make it create a review request.

### Exercise 2 — Add human approval

Before a high-value action, return:

```json
{"status": "awaiting_approval"}
```

and require explicit confirmation.

### Exercise 3 — Add memory

Persist customer notes in a JSON file or SQLite database.

### Exercise 4 — Add RAG

Replace `policies.json` with several policy documents and retrieve only the
relevant policy text.

### Exercise 5 — Add evaluation

Create 10 support scenarios and specify the expected tools and forbidden
actions for each one.

### Exercise 6 — Move to a graph/state-machine framework

Only after you understand this handwritten loop, rebuild it using a framework
such as LangGraph or an Agents SDK. You will then understand what the framework
is actually doing for you.

## Important learning point

Do not focus on "how many agents" yet.

First master:

```text
state
→ tool choice
→ tool execution
→ observation
→ next decision
→ verification
→ stop condition
```

Once this feels natural, multi-agent systems become much easier to understand.
