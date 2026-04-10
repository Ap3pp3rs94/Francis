"""
===============================================================================
Francis 2.0 — Custom Protocol Builder
Path: connectors/custom/custom_protocol_builder.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module builds and validates *custom protocol* specifications for connectors/custom/.

It enables:
  - Defining a protocol as a small JSON/YAML-like dict (we use Mapping[str, Any])
  - Validating protocol structure deterministically
  - Validating operation payloads/results against a *subset* of JSON Schema
  - Creating a runtime "client" wrapper that:
      * validates input payload
      * calls connector.call(operation, payload)
      * validates output payload
  - Generating lightweight docs and a Python stub to help developers implement protocols

GOALS
-----
- Provider/transport agnostic (HTTP, subprocess, MQTT, etc. can all use the same protocol spec)
- Safe-by-default: do not log raw payload bodies, tokens, or PII.
- Deterministic and minimal dependencies (standard library only).

SUPPORTED SCHEMA SUBSET
-----------------------
We support a pragmatic subset of JSON Schema-ish keywords:

Common:
  - type: "object" | "array" | "string" | "integer" | "number" | "boolean" | "null"
  - description
  - enum
  - const
  - default (ignored in validation)

Object:
  - properties: { name: schema }
  - required: [name...]
  - additionalProperties: bool | schema

Array:
  - items: schema
  - minItems / maxItems

String:
  - minLength / maxLength
  - pattern (regex)

Number / Integer:
  - minimum / maximum

Composition:
  - anyOf: [schema...]
  - oneOf: [schema...]
  - allOf: [schema...]

Refs:
  - $ref: "#/definitions/<Name>" or "#/$defs/<Name>" or "<Name>" (resolved from protocol definitions)

NOTES
-----
- This is not a full JSON Schema implementation (by design).
- For strict schemas, you can extend this module or wrap it with a stronger validator
  behind governance controls (e.g., jsonschema library).

===============================================================================
"""

from __future__ import annotations

import re
import textwrap
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from . import (
    CustomConnector,
    CustomConnectorInfo,
    CustomErrorContext,
    CustomValidationError,
    normalize_protocol_id,
    redact_value,
)

__all__ = [
    "CustomOperationSpec",
    "CustomProtocolSpec",
    "CustomCompiledOperation",
    "CustomProtocolClient",
    "build_protocol_spec",
    "compile_protocol",
    "build_client",
    "validate_payload",
    "generate_markdown_docs",
    "generate_python_stub",
]


# =============================================================================
# Spec dataclasses
# =============================================================================

Schema = Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class CustomOperationSpec:
    """
    One operation in a custom protocol.

    - name: operation name (must be a safe identifier-ish string)
    - input_schema/output_schema: schema dicts (JSON Schema subset)
    - idempotent: hint for caller retry policy (builder doesn't enforce retries)
    """

    name: str
    description: str | None = None

    input_schema: Schema | None = None
    output_schema: Schema | None = None

    idempotent: bool = True
    timeout_s: float | None = None

    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CustomProtocolSpec:
    """
    Protocol specification (validated, normalized).
    """

    protocol_id: str
    version: str | None = None
    description: str | None = None

    operations: Mapping[str, CustomOperationSpec] = field(default_factory=dict)

    # Shared schema definitions for $ref resolution
    definitions: Mapping[str, Schema] = field(default_factory=dict)

    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CustomCompiledOperation:
    """
    Compiled operation with validators.
    """

    spec: CustomOperationSpec
    validate_in: Callable[[Any], None]
    validate_out: Callable[[Any], None]


# =============================================================================
# Spec validation / building
# =============================================================================

_OP_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.\-]{0,63}$")


def _normalize_op_name(name: str) -> str:
    n = (name or "").strip()
    if not n:
        raise CustomValidationError("operation name is required", details={"field": "operation"})
    if "\r" in n or "\n" in n:
        raise CustomValidationError("operation name contains illegal newline characters")
    if not _OP_NAME_RE.match(n):
        raise CustomValidationError(
            "operation name has invalid format",
            details={"operation": redact_value(n), "expected": _OP_NAME_RE.pattern},
        )
    return n


def build_protocol_spec(spec: Mapping[str, Any]) -> CustomProtocolSpec:
    """
    Validate and normalize a protocol spec dict into a CustomProtocolSpec.

    Expected shape:
      {
        "protocol_id": "inventory_api",
        "version": "1.0",
        "description": "...",
        "definitions": { "Thing": { ...schema... }, ... },     # optional
        "operations": {
          "ping": { "description": "...", "input_schema": {...}, "output_schema": {...} },
          "get_item": { ... },
        },
        "meta": {...}                                          # optional
      }
    """
    if not isinstance(spec, Mapping):
        raise CustomValidationError("protocol spec must be a mapping/object")

    protocol_id = normalize_protocol_id(str(spec.get("protocol_id", "") or ""))
    version = spec.get("version")
    description = spec.get("description")
    meta = spec.get("meta") if isinstance(spec.get("meta"), Mapping) else {}

    defs_raw = spec.get("definitions") or spec.get("$defs") or {}
    if defs_raw and not isinstance(defs_raw, Mapping):
        raise CustomValidationError("definitions must be an object/mapping", details={"field": "definitions"})

    definitions: dict[str, Schema] = {}
    for k, v in (defs_raw or {}).items():
        name = str(k)
        if not name:
            continue
        if not isinstance(v, Mapping):
            raise CustomValidationError(
                "definition schema must be an object/mapping",
                details={"definition": redact_value(name)},
            )
        definitions[name] = v

    ops_raw = spec.get("operations")
    if not isinstance(ops_raw, Mapping) or not ops_raw:
        raise CustomValidationError("operations is required and must be an object/mapping")

    operations: dict[str, CustomOperationSpec] = {}
    for op_name_raw, op_spec_raw in ops_raw.items():
        op_name = _normalize_op_name(str(op_name_raw))

        if not isinstance(op_spec_raw, Mapping):
            raise CustomValidationError(
                "operation spec must be an object/mapping",
                details={"operation": op_name},
            )

        desc = op_spec_raw.get("description")
        input_schema = op_spec_raw.get("input_schema")
        output_schema = op_spec_raw.get("output_schema")

        if input_schema is not None and not isinstance(input_schema, Mapping):
            raise CustomValidationError(
                "input_schema must be an object/mapping if present",
                details={"operation": op_name},
            )

        if output_schema is not None and not isinstance(output_schema, Mapping):
            raise CustomValidationError(
                "output_schema must be an object/mapping if present",
                details={"operation": op_name},
            )

        idempotent = op_spec_raw.get("idempotent", True)
        idempotent = bool(idempotent)

        timeout_s = op_spec_raw.get("timeout_s")
        if timeout_s is not None:
            try:
                timeout_s = float(timeout_s)
            except Exception as exc:  # noqa: BLE001
                raise CustomValidationError("timeout_s must be a number", details={"operation": op_name}) from exc
            if timeout_s <= 0:
                raise CustomValidationError("timeout_s must be > 0", details={"operation": op_name})

        op_meta = op_spec_raw.get("meta") if isinstance(op_spec_raw.get("meta"), Mapping) else {}

        operations[op_name] = CustomOperationSpec(
            name=op_name,
            description=str(desc) if desc is not None else None,
            input_schema=input_schema,
            output_schema=output_schema,
            idempotent=idempotent,
            timeout_s=timeout_s,
            meta=op_meta,
        )

    return CustomProtocolSpec(
        protocol_id=protocol_id,
        version=str(version) if version is not None else None,
        description=str(description) if description is not None else None,
        operations=operations,
        definitions=definitions,
        meta=meta or {},
    )


# =============================================================================
# Schema validation (subset of JSON Schema)
# =============================================================================


def _resolve_ref(ref: str, definitions: Mapping[str, Schema]) -> Schema:
    r = (ref or "").strip()
    if not r:
        raise CustomValidationError("$ref is empty")

    # Common local forms
    #   #/definitions/Thing
    #   #/$defs/Thing
    #   #/schemas/Thing
    if r.startswith("#/"):
        parts = r[2:].split("/")
        if len(parts) >= 2:
            name = parts[-1]
        else:
            name = parts[0] if parts else ""
        if name in definitions:
            return definitions[name]
        raise CustomValidationError("unresolved $ref", details={"ref": redact_value(r)})

    # Allow plain name
    if r in definitions:
        return definitions[r]

    raise CustomValidationError("unresolved $ref", details={"ref": redact_value(r)})


def validate_payload(
    schema: Schema | None,
    value: Any,
    *,
    definitions: Mapping[str, Schema] | None = None,
    path: str = "$",
) -> None:
    """
    Validate a value against a schema (subset).

    Raises CustomValidationError on first validation failure.
    """
    defs = definitions or {}

    if schema is None:
        # No schema means "accept anything"
        return

    if not isinstance(schema, Mapping):
        raise CustomValidationError("schema must be an object/mapping", details={"path": path})

    # $ref resolution
    if "$ref" in schema:
        target = _resolve_ref(str(schema.get("$ref")), defs)
        validate_payload(target, value, definitions=defs, path=path)
        return

    # Composition
    if "allOf" in schema:
        all_of = schema.get("allOf")
        if not isinstance(all_of, Sequence):
            raise CustomValidationError("allOf must be a list", details={"path": path})
        for i, s in enumerate(all_of):
            if not isinstance(s, Mapping):
                raise CustomValidationError(
                    "allOf element must be a schema object", details={"path": f"{path}.allOf[{i}]"}
                )
            validate_payload(s, value, definitions=defs, path=path)
        return

    if "anyOf" in schema:
        any_of = schema.get("anyOf")
        if not isinstance(any_of, Sequence):
            raise CustomValidationError("anyOf must be a list", details={"path": path})
        last_err: CustomValidationError | None = None
        for i, s in enumerate(any_of):
            if not isinstance(s, Mapping):
                continue
            try:
                validate_payload(s, value, definitions=defs, path=path)
                return
            except CustomValidationError as ce:
                last_err = ce
        raise CustomValidationError("value does not match anyOf schemas", details={"path": path}) from last_err

    if "oneOf" in schema:
        one_of = schema.get("oneOf")
        if not isinstance(one_of, Sequence):
            raise CustomValidationError("oneOf must be a list", details={"path": path})
        matches = 0
        last_err: CustomValidationError | None = None
        for s in one_of:
            if not isinstance(s, Mapping):
                continue
            try:
                validate_payload(s, value, definitions=defs, path=path)
                matches += 1
            except CustomValidationError as ce:
                last_err = ce
        if matches != 1:
            raise CustomValidationError(
                "value must match exactly one schema in oneOf",
                details={"path": path, "matches": matches},
            ) from last_err
        return

    # const / enum
    if "const" in schema:
        if value != schema.get("const"):
            raise CustomValidationError("value does not match const", details={"path": path})
    if "enum" in schema:
        enum = schema.get("enum")
        if not isinstance(enum, Sequence) or isinstance(enum, (str, bytes)):
            raise CustomValidationError("enum must be a list", details={"path": path})
        if value not in enum:
            raise CustomValidationError("value not in enum", details={"path": path})

    # type
    typ = schema.get("type")
    if typ is None:
        # If no type, accept and just enforce enum/const/composition constraints above.
        return

    t = str(typ).strip().lower()

    def _is_int(x: Any) -> bool:
        return isinstance(x, int) and not isinstance(x, bool)

    def _is_num(x: Any) -> bool:
        return isinstance(x, (int, float)) and not isinstance(x, bool)

    if t == "null":
        if value is not None:
            raise CustomValidationError("expected null", details={"path": path})
        return

    if t == "boolean":
        if not isinstance(value, bool):
            raise CustomValidationError("expected boolean", details={"path": path})
        return

    if t == "integer":
        if not _is_int(value):
            raise CustomValidationError("expected integer", details={"path": path})
        _validate_num_bounds(schema, float(value), path=path)
        return

    if t == "number":
        if not _is_num(value):
            raise CustomValidationError("expected number", details={"path": path})
        _validate_num_bounds(schema, float(value), path=path)
        return

    if t == "string":
        if not isinstance(value, str):
            raise CustomValidationError("expected string", details={"path": path})
        _validate_string(schema, value, path=path)
        return

    if t == "array":
        if isinstance(value, (str, bytes, bytearray)):
            raise CustomValidationError("expected array (not string/bytes)", details={"path": path})
        if not isinstance(value, Sequence):
            raise CustomValidationError("expected array", details={"path": path})
        _validate_array(schema, value, definitions=defs, path=path)
        return

    if t == "object":
        if not isinstance(value, Mapping):
            raise CustomValidationError("expected object", details={"path": path})
        _validate_object(schema, value, definitions=defs, path=path)
        return

    raise CustomValidationError("unsupported schema type", details={"path": path, "type": redact_value(t)})


def _validate_num_bounds(schema: Schema, val: float, *, path: str) -> None:
    if "minimum" in schema:
        try:
            mn = float(schema.get("minimum"))
        except Exception:
            raise CustomValidationError("minimum must be numeric", details={"path": path})
        if val < mn:
            raise CustomValidationError("value below minimum", details={"path": path, "minimum": mn})
    if "maximum" in schema:
        try:
            mx = float(schema.get("maximum"))
        except Exception:
            raise CustomValidationError("maximum must be numeric", details={"path": path})
        if val > mx:
            raise CustomValidationError("value above maximum", details={"path": path, "maximum": mx})


def _validate_string(schema: Schema, s: str, *, path: str) -> None:
    if "minLength" in schema:
        try:
            mn = int(schema.get("minLength"))
        except Exception:
            raise CustomValidationError("minLength must be integer", details={"path": path})
        if len(s) < mn:
            raise CustomValidationError("string shorter than minLength", details={"path": path, "minLength": mn})
    if "maxLength" in schema:
        try:
            mx = int(schema.get("maxLength"))
        except Exception:
            raise CustomValidationError("maxLength must be integer", details={"path": path})
        if len(s) > mx:
            raise CustomValidationError("string longer than maxLength", details={"path": path, "maxLength": mx})
    if "pattern" in schema:
        pat = schema.get("pattern")
        try:
            rx = re.compile(str(pat))
        except Exception as exc:  # noqa: BLE001
            raise CustomValidationError("invalid regex pattern", details={"path": path}) from exc
        if not rx.search(s):
            raise CustomValidationError("string does not match pattern", details={"path": path})


def _validate_array(schema: Schema, arr: Sequence[Any], *, definitions: Mapping[str, Schema], path: str) -> None:
    if "minItems" in schema:
        try:
            mn = int(schema.get("minItems"))
        except Exception:
            raise CustomValidationError("minItems must be integer", details={"path": path})
        if len(arr) < mn:
            raise CustomValidationError("array shorter than minItems", details={"path": path, "minItems": mn})
    if "maxItems" in schema:
        try:
            mx = int(schema.get("maxItems"))
        except Exception:
            raise CustomValidationError("maxItems must be integer", details={"path": path})
        if len(arr) > mx:
            raise CustomValidationError("array longer than maxItems", details={"path": path, "maxItems": mx})

    items = schema.get("items")
    if items is None:
        return
    if not isinstance(items, Mapping):
        raise CustomValidationError("items must be a schema object", details={"path": path})
    for i, v in enumerate(arr):
        validate_payload(items, v, definitions=definitions, path=f"{path}[{i}]")


def _validate_object(schema: Schema, obj: Mapping[str, Any], *, definitions: Mapping[str, Schema], path: str) -> None:
    props = schema.get("properties") or {}
    if props and not isinstance(props, Mapping):
        raise CustomValidationError("properties must be an object", details={"path": path})

    required = schema.get("required") or []
    if required and (not isinstance(required, Sequence) or isinstance(required, (str, bytes))):
        raise CustomValidationError("required must be a list", details={"path": path})

    req_set = {str(x) for x in required} if required else set()
    for k in req_set:
        if k not in obj:
            raise CustomValidationError("missing required property", details={"path": f"{path}.{k}"})

    # Validate known properties
    for k, s in (props or {}).items():
        key = str(k)
        if key in obj:
            if not isinstance(s, Mapping):
                raise CustomValidationError("property schema must be an object", details={"path": f"{path}.{key}"})
            validate_payload(s, obj[key], definitions=definitions, path=f"{path}.{key}")

    # additionalProperties behavior
    addl = schema.get("additionalProperties", True)

    if addl is True or addl is None:
        return

    if addl is False:
        allowed = set(str(k) for k in (props or {}).keys())
        for k in obj.keys():
            if str(k) not in allowed:
                raise CustomValidationError("additional property not allowed", details={"path": f"{path}.{k}"})
        return

    # additionalProperties is a schema
    if isinstance(addl, Mapping):
        allowed = set(str(k) for k in (props or {}).keys())
        for k, v in obj.items():
            if str(k) in allowed:
                continue
            validate_payload(addl, v, definitions=definitions, path=f"{path}.{k}")
        return

    raise CustomValidationError("additionalProperties must be boolean or schema object", details={"path": path})


# =============================================================================
# Compilation + client wrapper
# =============================================================================


def compile_protocol(protocol: CustomProtocolSpec) -> Mapping[str, CustomCompiledOperation]:
    """
    Compile a protocol spec into per-operation validators.
    """
    if not isinstance(protocol, CustomProtocolSpec):
        raise CustomValidationError("protocol must be CustomProtocolSpec")

    compiled: dict[str, CustomCompiledOperation] = {}
    defs = protocol.definitions or {}

    for name, op in protocol.operations.items():

        def _vin(v: Any, *, _s=op.input_schema, _defs=defs) -> None:
            # If schema missing, accept any input; else validate.
            validate_payload(_s, v if v is not None else {}, definitions=_defs, path="$")

        def _vout(v: Any, *, _s=op.output_schema, _defs=defs) -> None:
            # If schema missing, accept any output.
            validate_payload(_s, v, definitions=_defs, path="$")

        compiled[name] = CustomCompiledOperation(spec=op, validate_in=_vin, validate_out=_vout)

    return compiled


class CustomProtocolClient:
    """
    Runtime client wrapper for a CustomConnector using a CustomProtocolSpec.

    Usage:
      spec = build_protocol_spec(protocol_dict)
      client = build_client(connector, spec)
      result = client.call("ping", {"x": 1})

    This wrapper validates inputs/outputs, but never logs raw payload bodies.
    """

    def __init__(self, connector: CustomConnector, protocol: CustomProtocolSpec) -> None:
        self._connector = connector
        self._protocol = protocol
        self._compiled = compile_protocol(protocol)

    @property
    def protocol(self) -> CustomProtocolSpec:
        return self._protocol

    @property
    def connector_info(self) -> CustomConnectorInfo:
        return self._connector.info()

    def operations(self) -> list[str]:
        return sorted(self._compiled.keys())

    def call(
        self,
        operation: str,
        payload: Mapping[str, Any] | None = None,
        *,
        identity: Any | None = None,
        timeout_s: float | None = None,
        validate_output: bool = True,
    ) -> Any:
        op = (operation or "").strip()
        if op not in self._compiled:
            raise CustomValidationError(
                "unknown operation",
                details={"operation": redact_value(op), "known": self.operations()},
                context=CustomErrorContext(
                    connector_id=self.connector_info.connector_id,
                    protocol_id=self._protocol.protocol_id,
                    operation="custom_protocol.call",
                ),
            )

        comp = self._compiled[op]
        payload_obj: Any = payload if payload is not None else {}

        # Validate input (never log payload)
        comp.validate_in(payload_obj)

        # Choose timeout: op.timeout_s overrides if caller didn't pass timeout_s
        eff_timeout = timeout_s if timeout_s is not None else comp.spec.timeout_s

        # Call connector
        result = self._connector.call(op, payload_obj, identity=identity, timeout_s=eff_timeout)

        # Validate output
        if validate_output:
            comp.validate_out(result)

        return result

    # Convenience: attribute-based call for operations
    def __getattr__(self, name: str) -> Any:
        # Allow client.ping(payload=...) style.
        if name in self._compiled:

            def _fn(
                payload: Mapping[str, Any] | None = None,
                *,
                identity: Any | None = None,
                timeout_s: float | None = None,
                validate_output: bool = True,
            ) -> Any:
                return self.call(
                    name,
                    payload,
                    identity=identity,
                    timeout_s=timeout_s,
                    validate_output=validate_output,
                )

            _fn.__name__ = name
            _fn.__doc__ = self._compiled[name].spec.description or f"Call operation '{name}'"
            return _fn
        raise AttributeError(name)


def build_client(connector: CustomConnector, protocol: CustomProtocolSpec) -> CustomProtocolClient:
    """Create a validated runtime client wrapper."""
    return CustomProtocolClient(connector, protocol)


# =============================================================================
# Docs + stub generation
# =============================================================================


def _schema_type_hint(schema: Schema | None) -> str:
    if not schema:
        return "Any"
    if "$ref" in schema:
        # Can't know without full resolution; keep Any.
        return "Any"
    t = schema.get("type")
    if not t:
        return "Any"
    tt = str(t).lower()
    if tt == "string":
        return "str"
    if tt == "integer":
        return "int"
    if tt == "number":
        return "float"
    if tt == "boolean":
        return "bool"
    if tt == "null":
        return "None"
    if tt == "array":
        return "list[Any]"
    if tt == "object":
        return "dict[str, Any]"
    return "Any"


def generate_markdown_docs(protocol: CustomProtocolSpec) -> str:
    """
    Generate a small operator/developer-friendly markdown doc for a protocol.
    """
    lines: list[str] = []
    lines.append(f"# Protocol: `{protocol.protocol_id}`")
    if protocol.version:
        lines.append(f"- Version: `{protocol.version}`")
    if protocol.description:
        lines.append("")
        lines.append(protocol.description.strip())

    lines.append("")
    lines.append("## Operations")
    for op_name in sorted(protocol.operations.keys()):
        op = protocol.operations[op_name]
        lines.append(f"### `{op.name}`")
        if op.description:
            lines.append(op.description.strip())
        lines.append("")
        lines.append(f"- Idempotent: `{bool(op.idempotent)}`")
        if op.timeout_s is not None:
            lines.append(f"- Default timeout: `{op.timeout_s}` seconds")
        lines.append(f"- Input: `{_schema_type_hint(op.input_schema)}`")
        lines.append(f"- Output: `{_schema_type_hint(op.output_schema)}`")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def generate_python_stub(protocol: CustomProtocolSpec, *, class_name: str = "GeneratedProtocolClient") -> str:
    """
    Generate a minimal Python client stub for IDE hints / implementation guidance.

    This is intentionally lightweight (types are approximate).
    """
    cls = (class_name or "GeneratedProtocolClient").strip()
    if not cls:
        cls = "GeneratedProtocolClient"

    ops = [protocol.operations[k] for k in sorted(protocol.operations.keys())]

    # Build methods
    methods: list[str] = []
    for op in ops:
        in_t = _schema_type_hint(op.input_schema)
        out_t = _schema_type_hint(op.output_schema)
        doc = (op.description or "").strip() or f"Call operation '{op.name}'."
        methods.append(
            textwrap.dedent(
                f"""
                def {op.name}(self, payload: {in_t} | None = None, *, timeout_s: float | None = None) -> {out_t}:
                    \"\"\"{doc}\"\"\"
                    raise NotImplementedError
                """
            ).strip()
        )

    body = "\n\n    ".join(methods) if methods else "pass"

    stub = f'''"""
Auto-generated client stub for protocol '{protocol.protocol_id}'.

This is a convenience scaffold. Runtime validation is provided by
connectors.custom.custom_protocol_builder.CustomProtocolClient.
"""

from __future__ import annotations
from typing import Any


class {cls}:
    protocol_id: str = "{protocol.protocol_id}"

    def __init__(self, connector: Any) -> None:
        self._connector = connector

    def call(self, operation: str, payload: Any | None = None, *, timeout_s: float | None = None) -> Any:
        return self._connector.call(operation, payload or {{}}, timeout_s=timeout_s)

    {body}
'''
    return stub
