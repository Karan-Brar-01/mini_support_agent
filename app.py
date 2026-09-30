import json
import os
from pathlib import Path
from typing import Any

def load_dotenv_if_present() -> None:
    """Tiny .env loader so local tool tests do not require extra packages."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_dotenv_if_present()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
MAX_AGENT_ROUNDS = 8



# -------------------------------------------------------------------
# Local "enterprise systems"
# These JSON files simulate an Order Management System, a policy store,
# and a Support Ticket system.
# -------------------------------------------------------------------

def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# -------------------------------------------------------------------
# TOOLS
# -------------------------------------------------------------------

def get_order(order_id: str) -> dict:
    """Look up one order."""
    orders = read_json(DATA_DIR / "orders.json")
    order = next((o for o in orders if o["order_id"] == order_id), None)

    if not order:
        return {
            "status": "error",
            "error": "order_not_found",
            "order_id": order_id,
        }

    return {"status": "success", "order": order}


def get_policy(topic: str) -> dict:
    """Retrieve a support policy by topic."""
    policies = read_json(DATA_DIR / "policies.json")
    policy = policies.get(topic)

    if not policy:
        return {
            "status": "error",
            "error": "policy_not_found",
            "topic": topic,
            "available_topics": list(policies.keys()),
        }

    return {
        "status": "success",
        "topic": topic,
        "policy": policy,
    }


def create_support_ticket(order_id: str, issue: str, priority: str) -> dict:
    """Create a support ticket in the local ticket system."""
    # Safety check: never create a ticket for a nonexistent order.
    order_result = get_order(order_id)
    if order_result["status"] != "success":
        return {
            "status": "error",
            "error": "cannot_create_ticket_for_unknown_order",
            "order_id": order_id,
        }

    tickets_path = DATA_DIR / "tickets.json"
    tickets = read_json(tickets_path)

    # Idempotency guard: don't create duplicate open tickets for the same
    # order + issue.
    existing = next(
        (
            t for t in tickets
            if t["order_id"] == order_id
            and t["issue"].lower() == issue.lower()
            and t["status"] == "open"
        ),
        None,
    )

    if existing:
        return {
            "status": "success",
            "created": False,
            "reason": "matching_open_ticket_already_exists",
            "ticket": existing,
        }

    ticket_id = f"T-{1000 + len(tickets) + 1}"
    ticket = {
        "ticket_id": ticket_id,
        "order_id": order_id,
        "issue": issue,
        "priority": priority,
        "status": "open",
    }
    tickets.append(ticket)
    write_json(tickets_path, tickets)

    return {
        "status": "success",
        "created": True,
        "ticket": ticket,
    }


def get_ticket(ticket_id: str) -> dict:
    """Verify/read a support ticket."""
    tickets = read_json(DATA_DIR / "tickets.json")
    ticket = next((t for t in tickets if t["ticket_id"] == ticket_id), None)

    if not ticket:
        return {
            "status": "error",
            "error": "ticket_not_found",
            "ticket_id": ticket_id,
        }

    return {"status": "success", "ticket": ticket}


TOOL_FUNCTIONS = {
    "get_order": get_order,
    "get_policy": get_policy,
    "create_support_ticket": create_support_ticket,
    "get_ticket": get_ticket,
}


# Tool schemas given to the model.
TOOLS = [
    {
        "type": "function",
        "name": "get_order",
        "description": (
            "Look up an order before making claims about its delivery status, "
            "customer, amount, or dates."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Order ID such as ORD-1002",
                }
            },
            "required": ["order_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_policy",
        "description": (
            "Retrieve company support policy. Use it before deciding what "
            "action is allowed for delivery problems."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": ["late_delivery", "refunds", "damaged_item"],
                }
            },
            "required": ["topic"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "create_support_ticket",
        "description": (
            "Create an operational support ticket when company policy says "
            "escalation is appropriate."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "issue": {
                    "type": "string",
                    "description": "Short factual description of the issue.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
            },
            "required": ["order_id", "issue", "priority"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_ticket",
        "description": (
            "Read a ticket by ID. Use this after ticket creation to verify "
            "that the requested action actually persisted."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
            },
            "required": ["ticket_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


AGENT_INSTRUCTIONS = """
You are a small Customer Support Operations Agent for Acme Store.

Your goal is to resolve or appropriately escalate order-support requests.

Rules:
1. Never invent order, policy, or ticket information.
2. For a question about a specific order, inspect the order with get_order.
3. Before deciding what action is allowed for a delivery/refund/damage issue,
   retrieve the relevant policy with get_policy.
4. If an order is marked delayed and company policy permits escalation,
   create a support ticket.
5. After creating a ticket, verify it using get_ticket before claiming success.
6. Do not create unnecessary tickets.
7. If a tool returns an error, adapt or explain the limitation.
8. Keep the final answer concise and tell the user what you checked and what
   action was actually completed.

You may call multiple tools over multiple rounds. Stop when the user's request
has been answered and any necessary action has been independently verified.
""".strip()


def call_tool(name: str, arguments_json: str) -> dict:
    """Dispatch one model-requested tool call."""
    try:
        args = json.loads(arguments_json)
    except json.JSONDecodeError:
        return {
            "status": "error",
            "error": "invalid_json_arguments",
        }

    function = TOOL_FUNCTIONS.get(name)
    if function is None:
        return {
            "status": "error",
            "error": "unknown_tool",
            "tool": name,
        }

    try:
        return function(**args)
    except TypeError as e:
        return {
            "status": "error",
            "error": "invalid_tool_arguments",
            "detail": str(e),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": "tool_execution_failed",
            "detail": str(e),
        }


def run_agent(user_request: str, verbose: bool = True) -> str:
    from openai import OpenAI

    client = OpenAI()
    """
    The core agent loop:

       user goal
          ↓
       model decides
          ↓
       tool call(s)
          ↓
       execute locally
          ↓
       observation
          ↓
       model decides again
          ↓
       final answer
    """
    input_items: list[Any] = [
        {"role": "user", "content": user_request}
    ]

    for round_number in range(1, MAX_AGENT_ROUNDS + 1):
        response = client.responses.create(
            model=MODEL,
            instructions=AGENT_INSTRUCTIONS,
            tools=TOOLS,
            input=input_items,
        )

        # Preserve ALL model output. This matters for multi-step tool use,
        # especially when reasoning items are part of the response.
        input_items += response.output

        tool_calls = [
            item for item in response.output
            if item.type == "function_call"
        ]

        if not tool_calls:
            return response.output_text or "Agent finished without text output."

        if verbose:
            print(f"\n--- Agent round {round_number} ---")

        for tool_call in tool_calls:
            if verbose:
                print(f"Tool requested: {tool_call.name}")
                print(f"Arguments: {tool_call.arguments}")

            result = call_tool(tool_call.name, tool_call.arguments)

            if verbose:
                print("Tool result:")
                print(json.dumps(result, indent=2))

            input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": tool_call.call_id,
                    "output": json.dumps(result),
                }
            )

    return (
        "Stopped because the agent exceeded the maximum number of tool rounds. "
        "Inspect the trace and agent instructions."
    )


def main() -> None:
    print("=" * 60)
    print("Mini Agentic AI Project: Customer Support Operations Agent")
    print(f"Model: {MODEL}")
    print("=" * 60)
    print("\nTry:")
    print('  My order ORD-1002 is late. Please investigate and help.')
    print('  What is happening with ORD-1001?')
    print('  My order ORD-9999 never arrived.')
    print("\nType 'exit' to quit.\n")

    while True:
        user_request = input("You: ").strip()

        if user_request.lower() in {"exit", "quit"}:
            break

        if not user_request:
            continue

        try:
            answer = run_agent(user_request)
            print(f"\nAgent: {answer}\n")
        except Exception as e:
            print(f"\nApplication error: {e}\n")


if __name__ == "__main__":
    main()
