"""Thin CLI wrapper for provisional cell asset admin actions used by the local UI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from battery_agent.provisional_cell_assets import (
    get_provisional_cell_asset,
    promote_provisional_cell_asset,
    review_provisional_cell_asset,
    search_provisional_cell_assets,
)


def _json_dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=True)


def _parse_json_string_list(payload: str | None) -> list[str]:
    if payload is None or not str(payload).strip():
        return []
    parsed = json.loads(payload)
    if not isinstance(parsed, list):
        raise ValueError("Expected a JSON array.")
    return [str(item).strip() for item in parsed if str(item).strip()]


def _parse_json_object(payload: str | None) -> dict[str, Any]:
    if payload is None or not str(payload).strip():
        return {}
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object.")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search")
    search.add_argument("--query", default=None)
    search.add_argument("--review-status", default=None)
    search.add_argument("--limit", type=int, default=25)

    load = subparsers.add_parser("load")
    load.add_argument("--provisional-id", required=True)

    review = subparsers.add_parser("review")
    review.add_argument("--provisional-id", required=True)
    review.add_argument("--decision", required=True)
    review.add_argument("--actor", required=True)
    review.add_argument("--review-notes-json", default="[]")
    review.add_argument("--corrected-fields-json", default="{}")
    review.add_argument("--required-field-waivers-json", default="[]")

    promote = subparsers.add_parser("promote")
    promote.add_argument("--provisional-id", required=True)
    promote.add_argument("--reviewer", required=True)
    promote.add_argument("--final-cell-id", default=None)
    promote.add_argument("--promotion-notes-json", default="[]")
    promote.add_argument("--replace-existing", action="store_true")

    return parser


def _run(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "search":
        return search_provisional_cell_assets(
            query=args.query,
            review_status=args.review_status,
            limit=args.limit,
        )
    if args.command == "load":
        return get_provisional_cell_asset(args.provisional_id)
    if args.command == "review":
        return review_provisional_cell_asset(
            args.provisional_id,
            decision=args.decision,
            actor=args.actor,
            review_notes=_parse_json_string_list(args.review_notes_json),
            corrected_fields=_parse_json_object(args.corrected_fields_json),
            required_field_waivers=_parse_json_string_list(
                args.required_field_waivers_json
            ),
        )
    if args.command == "promote":
        return promote_provisional_cell_asset(
            args.provisional_id,
            reviewer=args.reviewer,
            final_cell_id=args.final_cell_id,
            promotion_notes=_parse_json_string_list(args.promotion_notes_json),
            replace_existing=bool(args.replace_existing),
        )
    raise ValueError(f"Unsupported command: {args.command}")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        payload = _run(args)
    except KeyError as exc:
        payload = {
            "status": "error",
            "error_type": "unknown_provisional_cell_asset",
            "message": str(exc),
        }
    except ValueError as exc:
        payload = {
            "status": "error",
            "error_type": "provisional_asset_validation_error",
            "message": str(exc),
        }
    except json.JSONDecodeError as exc:
        payload = {
            "status": "error",
            "error_type": "invalid_json_payload",
            "message": exc.msg,
        }

    print(_json_dump(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
