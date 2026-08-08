"""Validate Claude Hook payload shapes without retaining sensitive values."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import os
from typing import Any, Dict, Optional, Tuple


_FIELD_ALIASES: Dict[str, Tuple[str, ...]] = {
    "event_type": ("hook_event_name", "event_type"),
    "failure_reason": ("reason", "failure_reason"),
    "session_name": ("session_name", "session_name_candidate"),
}
_REQUIRED_FIELDS = ("session_id", "cwd", "transcript_path", "event_type")


@dataclass(frozen=True)
class ValidationResult:
    """Safe validation outcome containing no input payload values."""

    accepted: bool
    error_code: Optional[str]
    evidence: Dict[str, Any]


def _value_for(payload: Mapping[str, Any], field: str) -> Tuple[bool, Any]:
    aliases = _FIELD_ALIASES.get(field, (field,))
    for alias in aliases:
        if alias in payload:
            return True, payload[alias]
    return False, None


def _valid_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _failure_reason_class(payload: Mapping[str, Any]) -> str:
    present, value = _value_for(payload, "failure_reason")
    if not present:
        return "missing"
    if not _valid_text(value):
        return "invalid"
    if value == "rate_limit":
        return "rate_limit"
    return "other"


def _presence_evidence(payload: Mapping[str, Any]) -> Dict[str, Any]:
    evidence: Dict[str, Any] = {
        "session_id_present": False,
        "cwd_present": False,
        "transcript_path_present": False,
        "event_type_present": False,
        "failure_reason_class": _failure_reason_class(payload),
        "session_name_present": False,
    }

    for field in ("session_id", "cwd", "transcript_path"):
        present, value = _value_for(payload, field)
        evidence["{}_present".format(field)] = present and _valid_text(value)

    event_present, event_value = _value_for(payload, "event_type")
    evidence["event_type_present"] = event_present and _valid_text(event_value)

    name_present, name_value = _value_for(payload, "session_name")
    evidence["session_name_present"] = name_present and _valid_text(name_value)
    return evidence


def _session_id_digest(payload: Mapping[str, Any]) -> Optional[str]:
    """Return an ephemeral correlation digest only when an explicit salt exists."""

    present, value = _value_for(payload, "session_id")
    salt = os.environ.get("AIPHEMETINE_CAPTURE_SALT")
    if not present or not _valid_text(value) or not salt:
        return None
    digest_input = (salt + "\x00" + value).encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()[:12]


def validate_hook_payload(payload: Any) -> ValidationResult:
    """Validate the safe minimum Hook contract.

    The returned result intentionally exposes only allowlisted error codes and
    boolean/classification evidence. It never stores or echoes payload values.
    """

    if not isinstance(payload, Mapping):
        return ValidationResult(
            accepted=False,
            error_code="payload_not_object",
            evidence={
                "session_id_present": False,
                "cwd_present": False,
                "transcript_path_present": False,
                "event_type_present": False,
                "failure_reason_class": "missing",
                "session_name_present": False,
            },
        )

    evidence = _presence_evidence(payload)
    for field in _REQUIRED_FIELDS:
        present, value = _value_for(payload, field)
        if not present:
            return ValidationResult(
                accepted=False,
                error_code="missing_{}".format(field),
                evidence=evidence,
            )
        if not _valid_text(value):
            return ValidationResult(
                accepted=False,
                error_code="invalid_{}".format(field),
                evidence=evidence,
            )

    if evidence["failure_reason_class"] == "invalid":
        return ValidationResult(
            accepted=False,
            error_code="invalid_failure_reason",
            evidence=evidence,
        )

    return ValidationResult(accepted=True, error_code=None, evidence=evidence)


def redact_hook_payload(payload: Any) -> Dict[str, Any]:
    """Return an evidence record safe for fixture reports and logs."""

    result = validate_hook_payload(payload)
    redacted = {
        "schema_version": 1,
        "accepted": result.accepted,
        "error_code": result.error_code,
        **result.evidence,
    }
    session_digest = _session_id_digest(payload) if isinstance(payload, Mapping) else None
    if session_digest is not None:
        redacted["session_id_digest"] = session_digest
    return redacted
