{# =============================================================================
  FRANCIS — plugins/templates/tool_safety_critical.tpl
  Tool specification template: SAFETY-CRITICAL RISK TIER

  Use this template for tools that can:
    - change real-world or high-impact digital state,
    - cause financial, legal, physical, or operational harm,
    - trigger industrial controls, security actions, credential operations,
    - perform destructive/irreversible steps,
    - or operate in regulated domains.

  Non-negotiables:
    - Default deny
    - Explicit scope allowlists
    - Strong approvals + trust gating (often multi-step)
    - Two-person rule / dual attestation where configured
    - Dry-run + simulation required where possible
    - Post-conditions verification + rollback plan
    - Immutable audit trail + tamper-evident logging
    - Strict redaction of all secrets/PII/regulated data
    - Rate limits and circuit breakers

  Template style:
    - YAML document
    - Jinja2 placeholders
    - Conservative defaults
    - Explicit schemas
============================================================================= #}

tool_spec_version: 1

tool:
  id: "{{ tool_id }}"
  name: "{{ tool_name }}"
  version: "{{ tool_version }}"
  risk_tier: "safety_critical"

  summary: "{{ tool_summary }}"
  description: |-
    {{ tool_description }}

  ownership:
    owner: "{{ owner }}"
    contact: "{{ contact }}"
    oncall: "{{ oncall | default('N/A') }}"
    escalation:
      governance_doc: "docs/GOVERNANCE.md"
      policies_doc: "docs/POLICIES.md"
      permission_doc: "docs/API_PERMISSIONS.md"
      threat_model_doc: "docs/THREAT_MODEL.md"
      trust_model_doc: "docs/TRUST_MODEL.md"
      safety_policy_docs:
        - "config/policies/safety_critical.yaml"
        - "config/policies/industrial_safety.yaml"
        - "config/policies/offensive_security.yaml"
        - "config/policies/privacy.yaml"
        - "config/policies/data_governance.yaml"
        - "config/policies/approvals.yaml"
        - "config/policies/api_permissions.yaml"

  tags:
{% if tags and tags|length > 0 %}
{% for t in tags %}
    - "{{ t }}"
{% endfor %}
{% else %}
    - "safety_critical"
    - "default_deny"
    - "two_person_rule"
    - "audited"
{% endif %}

  # ---------------------------------------------------------------------------
  # Execution wiring (must be heavily constrained)
  # ---------------------------------------------------------------------------
  execution:
    entrypoint: "{{ entrypoint }}"

    sandbox:
      enabled: true

      network:
        enabled: true
        policy_ref: "config/policies/networks.yaml"
        allowlist:
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
            - "config/*"
            - "data/state/*"
            - "data/system/*"
            - "data/trust/*"
{% endif %}
        write:
          enabled: true
          allowlist:
{% if fs_write_allowlist and fs_write_allowlist|length > 0 %}
{% for p in fs_write_allowlist %}
            - "{{ p }}"
{% endfor %}
{% else %}
            - "data/artifacts/*"
            - "data/logs/*"
            - "data/state/*"
{% endif %}

      environment:
        allow_vars:
{% if env_allowlist and env_allowlist|length > 0 %}
{% for v in env_allowlist %}
          - "{{ v }}"
{% endfor %}
{% else %}
          - "FRANCIS_ENV"
          - "FRANCIS_INSTANCE_ID"
{% endif %}
        deny_vars:
          - "OPENAI_API_KEY"
          - "AWS_SECRET_ACCESS_KEY"
          - "AZURE_CLIENT_SECRET"
          - "GCP_SERVICE_ACCOUNT"
          - "DATABASE_URL"
          - "TOKEN"
          - "PASSWORD"
          - "SECRET"

    timeouts:
      tool_seconds: {{ tool_timeout_seconds | default(120) }}
      operation_seconds: {{ op_timeout_seconds | default(90) }}

    retries:
      # Safety-critical operations must avoid blind retries.
      enabled: true
      max_attempts: {{ max_attempts | default(2) }}
      backoff: "exponential"
      retry_on:
        - "transient_network_error"
        - "rate_limited"
      never_retry_on:
        - "validation_error"
        - "permission_denied"
        - "policy_blocked"
        - "unsafe_precondition"
        - "postcondition_failed"
        - "partial_execution_detected"

    circuit_breakers:
      enabled: true
      failure_threshold: {{ breaker_failure_threshold | default(3) }}
      window_seconds: {{ breaker_window_seconds | default(300) }}
      cooloff_seconds: {{ breaker_cooloff_seconds | default(600) }}
      trip_on:
        - "postcondition_failed"
        - "unexpected_side_effect"
        - "integrity_violation"
        - "tamper_detected"

  # ---------------------------------------------------------------------------
  # Governance and required gates (strict)
  # ---------------------------------------------------------------------------
  gates:
    permission_gate:
      enabled: true
      default_deny: true
      policy_ref: "config/policies/api_permissions.yaml"
      delegation_required: true
      required_scopes:
{% if default_scopes and default_scopes|length > 0 %}
{% for s in default_scopes %}
        - "{{ s }}"
{% endfor %}
{% else %}
        - "REQUIRE_SCOPES"
{% endif %}

    trust_gate:
      enabled: true
      policy_ref: "config/policies/trust_boundaries.yaml"
      minimum_trust: "{{ default_trust_min | default('T3') }}"
      behavior: |-
        Trust must exceed minimum thresholds. For regulated domains, require
        elevated trust and additional approvals. Trust gate can force dry-runs,
        simulation-only execution, or human review.

    approvals_gate:
      enabled: true
      policy_ref: "config/policies/approvals.yaml"
      # Approval types are organization-defined. Keep explicit.
      required_approvals:
{% if required_approvals and required_approvals|length > 0 %}
{% for a in required_approvals %}
        - "{{ a }}"
{% endfor %}
{% else %}
        - "safety_critical_action"
{% endif %}
      # Optional: two-person rule for high impact actions.
      dual_attestation:
        enabled: {{ dual_attestation_enabled | default(true) }}
        required_roles:
          - "Operator"
          - "Reviewer"
        # Whether the same identity can satisfy both approvals:
        disallow_same_identity: true

    safety_gate:
      enabled: true
      policy_ref:
        - "config/policies/safety_critical.yaml"
        - "config/policies/industrial_safety.yaml"
        - "config/policies/offensive_security.yaml"
        - "config/policies/privacy.yaml"
        - "config/policies/data_governance.yaml"
        - "config/policies/regulated_domains.yaml"
      behavior: |-
        Blocks operations that violate safety constraints, regulated domain rules,
        privacy limits, or offensive-security restrictions.

    simulation_gate:
      # Require simulation/dry-run capability where possible.
      enabled: {{ simulation_required | default(true) }}
      policy_ref: "config/policies/sandbox.yaml"
      required: true
      acceptable_modes:
        - "dry_run"
        - "simulation"
      # The tool must provide a preview of intended changes and expected effects.
      requires_plan_preview: true

  # ---------------------------------------------------------------------------
  # Safety-critical execution contract
  # ---------------------------------------------------------------------------
  safety_contract:
    # Pre-conditions MUST be checked before execution.
    preconditions:
      required: true
      checks:
        - "scope_allows_operation_and_resource"
        - "approval_present_and_valid"
        - "trust_above_threshold"
        - "environment_mode_allows_action"
        - "rate_limit_ok"
        - "target_state_is_stable"
        - "idempotency_key_present_if_applicable"

    # Post-conditions MUST be verified after execution.
    postconditions:
      required: true
      checks:
        - "intended_change_applied"
        - "no_unintended_side_effects_detected"
        - "audit_event_written"
        - "rollback_plan_validated_if_partial"

    rollback:
      required: {{ rollback_required | default(true) }}
      # Tools should define rollback operations or safe undo patterns.
      strategy: "{{ rollback_strategy | default('best_effort_with_human_escalation') }}"
      escalation_on_failure: true

    idempotency:
      # Strongly recommended for external writes; enforce if available.
      required: {{ idempotency_required | default(true) }}
      key_field: "{{ idempotency_key_field | default('idempotency_key') }}"

  # ---------------------------------------------------------------------------
  # Telemetry: immutable audit and tamper-evidence
  # ---------------------------------------------------------------------------
  telemetry:
    audit:
      enabled: true
      location: "data/logs/audit/"
      immutable: true
      tamper_evident: true
      hash_chain:
        enabled: true
        algorithm: "{{ audit_hash_alg | default('sha256') }}"
        chain_file: "data/logs/audit/_hash_chain.jsonl"
      emit_events:
        - "tool.call.requested"
        - "tool.call.validated"
        - "tool.call.denied"
        - "tool.plan.preview_generated"
        - "tool.preconditions.checked"
        - "tool.call.executed"
        - "tool.postconditions.checked"
        - "tool.rollback.attempted"
        - "tool.rollback.completed"
        - "tool.call.resulted"
        - "tool.call.failed"
      include:
        request_id: true
        correlation_id: true
        actor_identity: true
        actor_role: true
        delegation_id: true
        scope_ids: true
        approval_ids: true
        trust_snapshot: true
        policy_snapshot_hash: true
        environment_mode: true
        tool_version: true
        # Never store full secrets; store only redacted forms and refs.
        redacted_inputs: true
        redacted_outputs: true

    metrics:
      enabled: true
      emit:
        - "latency_ms"
        - "success_rate"
        - "denial_rate"
        - "rollback_rate"
        - "postcondition_fail_rate"
        - "rate_limited_count"
        - "circuit_breaker_trips"

  redaction:
    enabled: true
    strategy: "field_and_pattern"
    fields:
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
      - "email"
      - "phone"
      - "ssn"
      - "address"
      - "dob"
    patterns:
      - "(?i)bearer\\s+[A-Za-z0-9\\-\\._~\\+\\/]+=*"
      - "(?i)eyJ[A-Za-z0-9_\\-]{10,}\\.[A-Za-z0-9_\\-]{10,}\\.[A-Za-z0-9_\\-]{10,}"
      - "(?i)(password|secret|token)\\s*[:=]\\s*[^\\s]+"

  # ---------------------------------------------------------------------------
  # Human interaction requirements (don’t allow silent high-impact writes)
  # ---------------------------------------------------------------------------
  human_in_the_loop:
    required: true
    ui_requirements:
      show:
        - "operation_summary"
        - "target_resources"
        - "diff_or_preview"
        - "risk_assessment"
        - "required_approvals"
        - "delegation_and_scopes"
        - "environment_mode"
        - "rollback_plan"
      confirm_phrases:
        # Use explicit, unambiguous confirmation strings if you enforce them.
        enabled: {{ confirm_phrases_enabled | default(false) }}
        phrase: "{{ confirm_phrase | default('CONFIRM') }}"

  explainability:
    required: true
    must_include:
      - "why_action_is_needed"
      - "what_will_change"
      - "which_policies_were_checked"
      - "which_scopes_and_delegations_were_used"
      - "which_approvals_were_used"
      - "trust_and_risk_summary"
      - "simulation_results_or_dry_run_preview"
      - "rollback_plan"
      - "postcondition_verification_results"
      - "confidence_and_uncertainties"
    refusal_style: |-
      If denied, explain missing approvals/scopes/trust or policy constraints at
      a safe level and propose a safer alternative (dry-run, narrower scope,
      added review, or escalation).

  # ---------------------------------------------------------------------------
  # Operations (must be explicit, schema-bound, and previewable)
  # ---------------------------------------------------------------------------
  operations:
{% if operations and operations|length > 0 %}
{% for op in operations %}
    - id: "{{ op.id }}"
      summary: "{{ op.summary }}"
      description: |-
        {{ op.description }}

      category: "{{ op.category | default('safety_critical') }}"
      reversible: {{ op.reversible | default(false) }}
      destructive: {{ op.destructive | default(false) }}

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
          - "safety_critical_action"
{% endif %}
        dual_attestation:
          enabled: {{ op.dual_attestation_enabled | default(true) }}
          disallow_same_identity: true

      execution_mode:
        supports:
          - "dry_run"
          - "simulation"
          - "execute"
        default: "dry_run"

      limits:
        # Very conservative; tune per tool.
        rate_limit:
          per_minute: {{ op.per_minute | default(10) }}
        max_targets: {{ op.max_targets | default(1) }}
        max_bytes: {{ op.max_bytes | default(2000000) }}

      # The tool MUST produce a preview/diff for the action.
      preview:
        required: true
        provides_diff: true
        diff_format: "{{ op.diff_format | default('unified') }}"

      input_schema:
        type: object
        additionalProperties: false
        properties:
          mode:
            type: string
            enum: ["dry_run", "simulation", "execute"]
            default: "dry_run"
          idempotency_key:
            type: string
            description: "Unique key to prevent duplicate execution."
          target:
            type: object
            description: "Structured target selector (resource constraints)."
          parameters:
            type: object
            description: "Operation parameters (validated)."
          justification:
            type: string
            description: "Human-readable reason; required for safety-critical actions."
        required:
          - "mode"
          - "target"
          - "justification"
          - "idempotency_key"

      output_schema:
        type: object
        additionalProperties: false
        properties:
          request_id: { type: string }
          allowed: { type: boolean }
          mode: { type: string }
          preview_diff:
            type: string
            description: "Diff/preview of intended changes (redacted)."
          executed: { type: boolean }
          rollback_available: { type: boolean }
          warnings:
            type: array
            items: { type: string }
          errors:
            type: array
            items: { type: string }
          postconditions:
            type: object
            description: "Results of postcondition checks."
        required:
          - "request_id"
          - "allowed"
          - "mode"
          - "executed"
{% endfor %}
{% else %}
    - id: "REPLACE_ME"
      summary: "Replace with a concrete safety-critical operation"
      description: |-
        Define at least one operation with preview, approval requirements, and
        strict schemas.

      category: "safety_critical"
      reversible: false
      destructive: false

      permissions:
        required_scopes:
          - "REQUIRE_SCOPES"
        methods:
          - "write"

      approvals:
        required:
          - "safety_critical_action"
        dual_attestation:
          enabled: true
          disallow_same_identity: true

      execution_mode:
        supports: ["dry_run", "simulation", "execute"]
        default: "dry_run"

      limits:
        rate_limit:
          per_minute: 10
        max_targets: 1
        max_bytes: 2000000

      preview:
        required: true
        provides_diff: true
        diff_format: "unified"

      input_schema:
        type: object
        additionalProperties: false
        properties:
          mode: { type: string, enum: ["dry_run", "simulation", "execute"], default: "dry_run" }
          idempotency_key: { type: string }
          target: { type: object }
          parameters: { type: object }
          justification: { type: string }
        required: ["mode", "target", "justification", "idempotency_key"]

      output_schema:
        type: object
        additionalProperties: false
        properties:
          request_id: { type: string }
          allowed: { type: boolean }
          mode: { type: string }
          preview_diff: { type: string }
          executed: { type: boolean }
          rollback_available: { type: boolean }
          warnings: { type: array, items: { type: string } }
          errors: { type: array, items: { type: string } }
          postconditions: { type: object }
        required: ["request_id", "allowed", "mode", "executed"]
{% endif %}

  # ---------------------------------------------------------------------------
  # Operator runbook hooks (optional but recommended)
  # ---------------------------------------------------------------------------
  runbook:
    required: {{ runbook_required | default(true) }}
    references:
      - "docs/RUNBOOK.md"
    on_incident:
      escalation_path:
        - "freeze_tool"
        - "revoke_delegation"
        - "trigger_emergency_shutdown"
        - "open_incident_ticket"
      evidence_preservation:
        - "snapshot_state"
        - "export_audit_trail"
        - "capture_tool_traces"

  # ---------------------------------------------------------------------------
  # Testing and certification expectations (safety-critical)
  # ---------------------------------------------------------------------------
  certification:
    required: true
    suites:
      - "tests/safety/*"
      - "tests/credential_security/*"
      - "tests/integration/*"
    required_properties:
      - "policy_compliance"
      - "idempotency"
      - "rollback_or_safe_abort"
      - "audit_integrity"
      - "redaction_correctness"
      - "simulation_accuracy_if_applicable"
    evidence_output:
      file: "data/trust/certifications/passed_tests.json"

  # ---------------------------------------------------------------------------
  # Examples
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
      description: "Generate a preview diff without executing"
      operation_id: "REPLACE_ME"
      input:
        mode: "dry_run"
        idempotency_key: "uuid-REPLACE"
        target:
          resource: "REPLACE"
        parameters:
          change: "REPLACE"
        justification: "REPLACE_WITH_HUMAN_JUSTIFICATION"
{% endif %}
