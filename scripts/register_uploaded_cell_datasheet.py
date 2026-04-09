"""Register one uploaded cell datasheet into the provisional review queue."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from battery_agent.cell_datasheet_extraction import (  # noqa: E402
    extract_cell_datasheet_candidate_from_text,
)
from battery_agent.provisional_cell_assets import (  # noqa: E402
    register_provisional_cell_asset,
)


def _json_dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=True)


def _sanitize_utf8_text(value: str) -> str:
    return re.sub(r"[\ud800-\udfff]", "\uFFFD", value)


def register_uploaded_cell_datasheet_payload(payload: dict[str, Any]) -> dict[str, Any]:
    file_path = _sanitize_utf8_text(str(payload.get("file_path") or "").strip())
    attachment_text = _sanitize_utf8_text(str(payload.get("attachment_text") or ""))
    submitted_by = (
        _sanitize_utf8_text(str(payload.get("submitted_by") or "chat_user").strip())
        or "chat_user"
    )
    submit_for_review = bool(payload.get("submit_for_review"))

    if not file_path:
        raise ValueError("file_path is required.")
    if not attachment_text.strip():
        raise ValueError("attachment_text is required.")

    extraction_payload = extract_cell_datasheet_candidate_from_text(
        attachment_text,
        thread_file_path=file_path,
    )
    candidate = extraction_payload.get("candidate", extraction_payload)
    if not isinstance(candidate, dict):
        raise ValueError("Structured datasheet extraction did not return a candidate object.")

    return register_provisional_cell_asset(
        candidate,
        submitted_by=submitted_by,
        source_file=file_path,
        extraction_status="machine_extracted",
        parser_version=str(
            extraction_payload.get("parser_version")
            or candidate.get("parser_version")
            or "openai_gpt4o_cell_datasheet_v1"
        ),
        submit_for_review=submit_for_review,
    )


def _load_stdin_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("Expected JSON payload on stdin.")

    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object on stdin.")
    return parsed


def main() -> int:
    try:
        payload = _load_stdin_payload()
        result = register_uploaded_cell_datasheet_payload(payload)
    except KeyError as exc:
        result = {
            "status": "error",
            "error_type": "uploaded_thread_file_not_found",
            "message": str(exc),
        }
    except ValueError as exc:
        result = {
            "status": "error",
            "error_type": "provisional_asset_validation_error",
            "message": str(exc),
        }
    except json.JSONDecodeError as exc:
        result = {
            "status": "error",
            "error_type": "invalid_json_payload",
            "message": exc.msg,
        }
    except RuntimeError as exc:
        result = {
            "status": "error",
            "error_type": "datasheet_extraction_runtime_error",
            "message": str(exc),
        }

    print(_json_dump(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
