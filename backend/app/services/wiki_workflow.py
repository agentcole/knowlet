from __future__ import annotations

from copy import deepcopy

WORKFLOW_KEY = "wiki_workflow"
DEFAULT_CATEGORY = "General"
VALID_ACTIONS = {"create_new", "append", "replace"}


def get_workflow(metadata: dict | None) -> dict:
    if not isinstance(metadata, dict):
        return {"state": "processing"}

    workflow = metadata.get(WORKFLOW_KEY)
    if isinstance(workflow, dict):
        return deepcopy(workflow)
    return {"state": "processing"}


def set_workflow(metadata: dict | None, workflow: dict) -> dict:
    base = deepcopy(metadata) if isinstance(metadata, dict) else {}
    base[WORKFLOW_KEY] = workflow
    return base


def normalize_placement(placement: dict | None) -> dict | None:
    if not isinstance(placement, dict):
        return None

    category_name = str(placement.get("category_name") or "").strip() or DEFAULT_CATEGORY
    page_title = str(placement.get("page_title") or "").strip()
    action = str(placement.get("action") or "create_new").strip().lower()
    if action not in VALID_ACTIONS:
        action = "create_new"

    if not page_title:
        return None

    normalized = {
        "category_name": category_name,
        "page_title": page_title,
        "action": action,
    }

    reasoning = placement.get("reasoning")
    if isinstance(reasoning, str) and reasoning.strip():
        normalized["reasoning"] = reasoning.strip()

    confidence = placement.get("confidence")
    if isinstance(confidence, (int, float)):
        normalized["confidence"] = float(confidence)

    return normalized
