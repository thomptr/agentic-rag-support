#!/usr/bin/env bash
# Register the three executor tools as AgentCore Gateway Targets.
#
# AWSCC v1.83.0 does not yet expose `awscc_bedrockagentcore_gateway_target`,
# so this side-channel script fills the gap. Idempotent — re-running it
# updates existing targets rather than creating duplicates.
#
# Requires: .venv with boto3 (already a project dependency). Reads outputs
# from `tofu -chdir=infra/environments/dev output -json`.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "${REPO_ROOT}/.venv/bin/python" - <<'PY'
import json
import subprocess
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REPO = Path(__file__).resolve()
# When invoked via heredoc, __file__ is "<stdin>". Resolve via env REPO_ROOT.
import os
REPO_ROOT = Path(os.environ.get("REPO_ROOT") or os.getcwd())
sys.path.insert(0, str(REPO_ROOT))

from lambdas.create_ticket.schema import CreateTicketInput, CreateTicketOutput
from lambdas.issue_refund.schema import IssueRefundInput, IssueRefundOutput
from lambdas.order_status.schema import OrderStatusInput, OrderStatusOutput

REGION = "us-east-1"

# --- Read OpenTofu outputs ----------------------------------------------------
tf = subprocess.run(
    ["tofu", "-chdir=" + str(REPO_ROOT / "infra/environments/dev"), "output", "-json"],
    capture_output=True, text=True, check=True,
)
outputs = json.loads(tf.stdout)
GATEWAY_ID = outputs["gateway_id"]["value"]
LAMBDA_NAMES = outputs["lambda_function_names"]["value"]
ACCOUNT = boto3.client("sts").get_caller_identity()["Account"]

def lambda_arn(fn_name: str) -> str:
    return f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:{fn_name}"

# --- MCP tool schemas (subset of JSON Schema accepted by AgentCore Gateway) ---
def to_mcp_schema(model_cls) -> dict:
    """Project Pydantic JSON Schema to the shape AgentCore expects.

    The Bedrock AgentCore CreateGatewayTarget inputSchema accepts:
      type (string), properties (map of string->JSON Schema), required (list),
      items (single nested schema for arrays), description (string).
    No $defs, no anyOf — flatten as needed.
    """
    raw = model_cls.model_json_schema()
    out: dict = {"type": raw.get("type", "object")}
    if "description" in raw:
        out["description"] = raw["description"]
    if "properties" in raw:
        out["properties"] = {k: _strip_schema(v) for k, v in raw["properties"].items()}
    if "required" in raw:
        out["required"] = list(raw["required"])
    return out


def envelope_schema(model_cls) -> dict:
    """Wrap the per-tool input schema in the contract envelope the Lambdas
    actually expect: `{tool_name, parameters, trace_meta}`. The Gateway passes
    the MCP `arguments` straight through as the Lambda event, so the schema
    we register here MUST match the Lambda's `event[...]` reads — not the raw
    parameter object. (See contracts/tool-lambda.md.)"""
    return {
        "type": "object",
        "properties": {
            "tool_name": {
                "type": "string",
                "description": "Lambda's internal TOOL_NAME constant.",
            },
            "parameters": to_mcp_schema(model_cls),
            "trace_meta": {
                "type": "object",
                "description": "Langfuse trace continuity metadata.",
                "properties": {
                    "trace_id": {"type": "string"},
                    "parent_span_id": {"type": "string"},
                    "session_id": {"type": "string"},
                    "run_id": {"type": "string"},
                },
                "required": ["trace_id", "parent_span_id"],
            },
        },
        "required": ["tool_name", "parameters", "trace_meta"],
    }


def _strip_schema(prop: dict) -> dict:
    """Project a Pydantic JSON Schema property to AgentCore-acceptable shape.

    Keeps type/description/items. Flattens `anyOf` containing exactly one
    non-null type (the common `X | None` optional) to that type. Defaults to
    "string" if no type can be inferred.
    """
    out: dict = {}
    if "type" in prop:
        out["type"] = prop["type"]
    elif "anyOf" in prop:
        non_null = [m for m in prop["anyOf"] if m.get("type") != "null"]
        if len(non_null) == 1 and "type" in non_null[0]:
            out["type"] = non_null[0]["type"]
        else:
            out["type"] = "string"
    else:
        out["type"] = "string"
    if "description" in prop:
        out["description"] = prop["description"]
    if "items" in prop:
        out["items"] = _strip_schema(prop["items"])
    return out


TARGETS = [
    {
        # target_name = Gateway resource ID (regex forbids underscores)
        # tool_name = MCP tool name surfaced to the agent (underscores OK)
        "tool_key": "create_ticket",
        "target_name": "create-ticket",
        "tool_name": "create_ticket",
        "description": "Create a new customer support ticket.",
        "input_model": CreateTicketInput,
        "output_model": CreateTicketOutput,
    },
    {
        "tool_key": "issue_refund",
        "target_name": "issue-refund",
        "tool_name": "issue_refund",
        "description": "Issue a refund for a customer order. Requires customer_id.",
        "input_model": IssueRefundInput,
        "output_model": IssueRefundOutput,
    },
    {
        "tool_key": "order_status",
        "target_name": "order-status",
        "tool_name": "order_status",
        "description": "Look up the current status of a customer order.",
        "input_model": OrderStatusInput,
        "output_model": OrderStatusOutput,
    },
]

# --- Reconcile gateway targets ------------------------------------------------
client = boto3.client("bedrock-agentcore-control", region_name=REGION)

existing = {
    t["name"]: t["targetId"]
    for t in client.list_gateway_targets(gatewayIdentifier=GATEWAY_ID).get("items", [])
}

for t in TARGETS:
    tool_payload = {
        "name": t["tool_name"],
        "description": t["description"],
        "inputSchema": envelope_schema(t["input_model"]),
        "outputSchema": to_mcp_schema(t["output_model"]),
    }
    target_config = {
        "mcp": {
            "lambda": {
                "lambdaArn": lambda_arn(LAMBDA_NAMES[t["tool_key"]]),
                "toolSchema": {"inlinePayload": [tool_payload]},
            }
        }
    }

    # Lambda targets use the Gateway's IAM role (which we granted
    # lambda:InvokeFunction on the per-tool ARNs) — no per-target credentials.
    creds = [{"credentialProviderType": "GATEWAY_IAM_ROLE"}]

    if t["target_name"] in existing:
        target_id = existing[t["target_name"]]
        print(f"==> Updating target {t['target_name']} ({target_id})")
        client.update_gateway_target(
            gatewayIdentifier=GATEWAY_ID,
            targetId=target_id,
            name=t["target_name"],
            description=t["description"],
            targetConfiguration=target_config,
            credentialProviderConfigurations=creds,
        )
    else:
        print(f"==> Creating target {t['target_name']} (MCP tool name: {t['tool_name']})")
        try:
            client.create_gateway_target(
                gatewayIdentifier=GATEWAY_ID,
                name=t["target_name"],
                description=t["description"],
                targetConfiguration=target_config,
                credentialProviderConfigurations=creds,
            )
        except ClientError as exc:
            print(f"!! Create failed for {t['target_name']}: {exc}", file=sys.stderr)
            raise

print()
print("==> Final target list:")
for t in client.list_gateway_targets(gatewayIdentifier=GATEWAY_ID).get("items", []):
    print(f"   - {t['name']:20s} status={t.get('status', '?')} id={t['targetId']}")
PY
