{# =============================================================================
  FRANCIS — plugins/templates/tool_critical.tpl
  Tool specification template: CRITICAL RISK TIER

  Use this template for tools that can:
    - modify external systems (write/update),
    - trigger side effects (messages, tickets, deployments),
    - change persistent state (DB writes),
    - or otherwise create material operational impact.

  CRITICAL ≠ SAFETY-CRITICAL:
    - SAFETY-CRITICAL is reserved for actions that can directly endanger humans,
      industrial actuators, irreversible destructive operations, etc.
    - CRITICAL is “high-impact but generally recoverable with proper controls.”

  Template style:
    - YAML document
    - Jinja2 placeholders
    - Safe defaults: deny unless explicitly granted and approved by policy.

  Expected template inputs (recommended):
    tool_id: string (stable, snake_case)
    tool_name: string (human readable)
    tool_version: string (semver)
    tool_summary: string (one-liner)
    tool_description: string (longer description)
    owner: string (team/person)
    contact: string (email/slack channel)
    entrypoint: string (python module:function or executable reference)
    operations: list of objects (see operations block)
    default_scopes: list[string] (scope ids)
    default_approvals: list[string] (approval types)
    default_trust_min: string (e.g., "T2", "T3", "T4") or numeric
    tags: list[string]
    examples: list of example calls (optional)

  NOTE:
    - Keep additionalProperties: false in JSON schemas.
    - Prefer explicit allowlists over blocklists.
    - Ensure dry_run and idempotency are supported for critical operations.
============================================================================= #}

tool_spec_version: 1

tool:
  id: "{{ tool_id }}"
  name: "{{ tool_name }}"
  version: "{{ tool_version }}"
  risk_tier: "critical"

  summary: "{{ tool_summary }}"
  description: |-
    {{ tool_description }}

  ownership:
    owner: "{{ owner }}"
    contact: "{{ contact }}"
    escalation:
      policy_doc: "docs/GOVERNANCE.md"
      approvals_doc: "config/policies/approvals.yaml"
      permission_doc: "docs/API_PERMISSIONS.md"
      trust_doc: "docs/TRUST_MODEL.md"
      threat_model_doc: "docs/THREAT_MODEL.md"

  tags:
{% if tags and tags|length > 0 %}
{% for t in tags %}
    - "{{ t }}"
{% endfor %}
{% else %}
    - "critical"
    - "governed"
    - "audited"
{% endif %}

  # ---------------------------------------------------------------------------
  # Execution wiring
  # ---------------------------------------------------------------------------
  execution:
    entrypoint: "{{ entrypoint }}"

    # Critical tools must be bounded.
    sandbox:
      enabled: true
      network:
        # Network may be needed for SaaS connectors; keep explicit and policy-gated.
        enabled: true
        policy_ref: "config/policies/networks.yaml"
        allowlist:
          # Prefer explicit domains/services if possible.
{% if network_allowlist and network_allowlist|length > 0 %}
{% for host in network_allowlist %}
          - "{{ host }}"
{% endfor %}
{% else %}
          - "REQUIRE_EXPLICIT_ALLOWLIST"
{% endif %}
      filesystem:
        read:
          enabled: true
          allowlist:
{% if fs_read_allowlist and fs_read_allowlist|length > 0 %}
{% for p in fs_read_allowlist %}
            - "{{ p }}"
{% endfor %}
{% else %}
            - "data/uploads/*"
            - "data/artifacts/*"
{% endif %}
        write:
          # Writes are allowed only when explicitly needed for tool outputs.
          enabled: true
          allowlist:
{% if fs_write_allowlist and fs_write_allowlist|length > 0 %}
{% for p in fs_write_allowlist %}
            - "{{ p }}"
{% endfor %}
{% else %}
            - "data/artifacts/*"
            - "data/logs/*"
{% endif %}

    timeouts:
      # Keep conservative defaults; override per operation if needed.
      tool_seconds: {{ tool_timeout_seconds | default(60) }}
      operation_seconds: {{ op_timeout_seconds | default(45) }}

    retries:
      # Retries are dangerous for side-effecting operations.
      # Use idempotency + safe retry rules.
      enabled: true
      max_attempts: {{ max_attempts | default(2) }}
      backoff: "exponential"
      retry_on:
        - "transient_network_error"
        - "rate_limited"
        - "timeout"
      never_retry_on:
        - "validation_error"
        - "permission_denied"
        - "approval_required"
        - "policy_blocked"
        - "already_committed_non_idempotent"

    idempotency:
      required: true
      key_field: "idempotency_key"
      semantics: |-
        Critical operations MUST support idempotency.
        If a request is repeated with the same idempotency_key, the tool must:
          - return the original result (or a stable reference),
          - never perform the side effect twice.

    dry_run:
      supported: true
      parameter: "dry_run"
      semantics: |-
        When dry_run=true, the tool must:
          - perform validation and policy checks,
          - compute a plan/preview,
          - produce an execution diff or impact summary,
          - perform zero external writes/side effects.

  # ---------------------------------------------------------------------------
  # Governance + security gates (must all pass)
  # ---------------------------------------------------------------------------
  gates:
    permission_gate:
      enabled: true
      default_deny: true
      policy_ref: "config/policies/api_permissions.yaml"
      required_scopes:
{% if default_scopes and default_scopes|length > 0 %}
{% for s in default_scopes %}
        - "{{ s }}"
{% endfor %}
{% else %}
        - "REQUIRE_SCOPES"
{% endif %}
      delegation_required: true
      separation_of_duties:
        enforced: true
        rationale: |-
          Critical tools should not allow one actor to propose, approve, and execute
          high-impact changes without independent review when policy requires it.

    trust_gate:
      enabled: true
      policy_ref: "config/policies/trust_boundaries.yaml"
      minimum_trust: "{{ default_trust_min | default('T3') }}"
      behavior: |-
        If trust is below minimum:
          - require dry-run OR
          - require explicit human approval OR
          - deny with actionable remediation.

    approvals_gate:
      enabled: true
      policy_ref: "config/policies/approvals.yaml"
      required_approvals:
{% if default_approvals and default_approvals|length > 0 %}
{% for a in default_approvals %}
        - "{{ a }}"
{% endfor %}
{% else %}
        - "critical_write"
{% endif %}
      approval_scope: "per_action_hash"
      emergency_override:
        allowed: true
        requires:
          - "emergency_approval"
        audit_level: "highest"

    safety_gate:
      enabled: true
      policy_ref:
        - "config/policies/human_safety.yaml"
        - "config/policies/offensive_security.yaml"
        - "config/policies/privacy.yaml"
        - "config/policies/data_governance.yaml"
      behavior: |-
        The safety gate may block tool execution even when permissions allow it.
        The block must be logged with rationale (redacted) and policy references.

  # ---------------------------------------------------------------------------
  # Telemetry, auditability, and redaction
  # ---------------------------------------------------------------------------
  telemetry:
    audit:
      enabled: true
      policy_ref: "docs/API_PERMISSIONS.md"
      emit_events:
        - "tool.call.requested"
        - "tool.call.validated"
        - "tool.call.denied"
        - "tool.call.approval_required"
        - "tool.call.executed"
        - "tool.call.resulted"
        - "tool.call.failed"
      include:
        request_id: true
        correlation_id: true
        actor_identity: true
        delegation_id: true
        scope_ids: true
        policy_snapshot_hash: true
        tool_version: true
      retention:
        # Logging retention is configured globally; this is a declaration of intent.
        class: "operational_audit"
        location: "data/logs/audit/"
    metrics:
      enabled: true
      emit:
        - "latency_ms"
        - "success_rate"
        - "denial_rate"
        - "approval_latency_ms"
        - "retry_count"
        - "dry_run_usage_rate"

  redaction:
    enabled: true
    strategy: "field_and_pattern"
    fields:
      # Common secret carriers (case-insensitive matching recommended).
      - "api_key"
      - "token"
      - "access_token"
      - "refresh_token"
      - "authorization"
      - "cookie"
      - "set_cookie"
      - "password"
      - "secret"
      - "private_key"
      - "client_secret"
      - "session"
    patterns:
      # Keep conservative: redact anything that looks like a bearer token / JWT / key block.
      - "(?i)bearer\\s+[A-Za-z0-9\\-\\._~\\+\\/]+=*"
      - "(?i)eyJ[A-Za-z0-9_\\-]{10,}\\.[A-Za-z0-9_\\-]{10,}\\.[A-Za-z0-9_\\-]{10,}"   # JWT-ish
      - "-----BEGIN ([A-Z ]+)?PRIVATE KEY-----[\\s\\S]*?-----END ([A-Z ]+)?PRIVATE KEY-----"

  # ---------------------------------------------------------------------------
  # Human-facing behavior contract (critical tools must explain themselves)
  # ---------------------------------------------------------------------------
  explainability:
    required: true
    must_include:
      - "what_will_happen"
      - "what_will_change"
      - "why_this_is_allowed"
      - "which_policies_were_checked"
      - "which_scopes_and_delegations_were_used"
      - "rollback_or_recovery_plan"
      - "confidence_and_uncertainties"
    refusal_style: |-
      If denied, explain at a safe level:
        - what category of rule blocked it,
        - what evidence/approval/scope is missing,
        - what safer alternative exists,
        - never reveal secrets or sensitive internals.

  # ---------------------------------------------------------------------------
  # Operations
  # ---------------------------------------------------------------------------
  operations:
{% if operations and operations|length > 0 %}
{% for op in operations %}
    - id: "{{ op.id }}"
      summary: "{{ op.summary }}"
      description: |-
        {{ op.description }}

      side_effects:
        expected: {{ op.side_effects_expected | default(true) }}
        reversible: {{ op.reversible | default(true) }}
        rollback: |-
{% if op.rollback %}
          {{ op.rollback }}
{% else %}
          Provide rollback guidance:
            - how to revert the change,
            - where to find the audit record,
            - what to monitor post-change.
{% endif %}

      permissions:
        required_scopes:
{% if op.required_scopes and op.required_scopes|length > 0 %}
{% for s in op.required_scopes %}
          - "{{ s }}"
{% endfor %}
{% else %}
          - "INHERIT_DEFAULT_SCOPES"
{% endif %}
        methods:
{% if op.methods and op.methods|length > 0 %}
{% for m in op.methods %}
          - "{{ m }}"
{% endfor %}
{% else %}
          - "write"
{% endif %}

      approvals:
        required:
{% if op.required_approvals and op.required_approvals|length > 0 %}
{% for a in op.required_approvals %}
          - "{{ a }}"
{% endfor %}
{% else %}
          - "critical_write"
{% endif %}
        allow_emergency_override: {{ op.allow_emergency_override | default(true) }}

      trust:
        minimum: "{{ op.minimum_trust | default(default_trust_min | default('T3')) }}"
        on_low_trust: "{{ op.on_low_trust | default('require_approval_or_dry_run') }}"

      execution:
        timeout_seconds: {{ op.timeout_seconds | default(op_timeout_seconds | default(45)) }}
        supports_dry_run: {{ op.supports_dry_run | default(true) }}
        supports_idempotency: {{ op.supports_idempotency | default(true) }}

      # OpenAI-style tool schema (function calling)
      # NOTE: Keep additionalProperties false to avoid injection via unknown keys.
      input_schema:
        type: object
        additionalProperties: false
        properties:
          dry_run:
            type: boolean
            default: false
            description: "If true: validate + preview only; no side effects."
          idempotency_key:
            type: string
            minLength: 8
            maxLength: 128
            description: "Client-supplied idempotency key for safe retries."
{% if op.input_properties %}
{% for k, v in op.input_properties.items() %}
          {{ k }}:
{% for line in v.split('\n') %}
            {{ line }}
{% endfor %}
{% endfor %}
{% else %}
          payload:
            type: object
            additionalProperties: false
            description: "Operation-specific payload (replace with explicit fields)."
{% endif %}
        required:
          - "dry_run"
          - "idempotency_key"
{% if op.required_fields %}
{% for rf in op.required_fields %}
          - "{{ rf }}"
{% endfor %}
{% endif %}

      output_schema:
        type: object
        additionalProperties: false
        properties:
          request_id:
            type: string
            description: "Correlation id for audit trail."
          dry_run:
            type: boolean
          allowed:
            type: boolean
            description: "True if all gates passed (and executed if dry_run=false)."
          approvals_used:
            type: array
            items: { type: string }
          scopes_used:
            type: array
            items: { type: string }
          changes:
            type: object
            description: "Diff/impact summary for preview and execution."
          result:
            type: object
            description: "Operation result payload."
          warnings:
            type: array
            items: { type: string }
        required:
          - "request_id"
          - "dry_run"
          - "allowed"

{% endfor %}
{% else %}
    - id: "REPLACE_ME"
      summary: "Replace with a concrete operation"
      description: |-
        Define at least one operation. Critical tools must have explicit, typed
        inputs and an explainable, auditable output.

      side_effects:
        expected: true
        reversible: true
        rollback: |-
          Document rollback steps here.

      permissions:
        required_scopes:
          - "REQUIRE_SCOPES"
        methods:
          - "write"

      approvals:
        required:
          - "critical_write"
        allow_emergency_override: true

      trust:
        minimum: "{{ default_trust_min | default('T3') }}"
        on_low_trust: "require_approval_or_dry_run"

      execution:
        timeout_seconds: {{ op_timeout_seconds | default(45) }}
        supports_dry_run: true
        supports_idempotency: true

      input_schema:
        type: object
        additionalProperties: false
        properties:
          dry_run: { type: boolean, default: false }
          idempotency_key: { type: string, minLength: 8, maxLength: 128 }
          payload: { type: object, additionalProperties: false }
        required: ["dry_run", "idempotency_key", "payload"]

      output_schema:
        type: object
        additionalProperties: false
        properties:
          request_id: { type: string }
          dry_run: { type: boolean }
          allowed: { type: boolean }
          changes: { type: object }
          result: { type: object }
          warnings: { type: array, items: { type: string } }
        required: ["request_id", "dry_run", "allowed"]
{% endif %}

  # ---------------------------------------------------------------------------
  # Examples (optional but recommended)
  # ---------------------------------------------------------------------------
  examples:
{% if examples and examples|length > 0 %}
{% for ex in examples %}
    - name: "{{ ex.name }}"
      description: "{{ ex.description }}"
      operation_id: "{{ ex.operation_id }}"
      input:
{% for line in ex.input_yaml.split('\n') %}
        {{ line }}
{% endfor %}
{% endfor %}
{% else %}
    - name: "dry_run_preview"
      description: "Show impact without executing"
      operation_id: "REPLACE_ME"
      input:
        dry_run: true
        idempotency_key: "example-00000001"
        payload: {}
{% endif %}
