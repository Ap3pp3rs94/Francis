{# =============================================================================
  FRANCIS — plugins/templates/tool_readonly.tpl
  Tool specification template: READ-ONLY RISK TIER

  Use this template for tools that:
    - do not write external state,
    - do not perform irreversible actions,
    - and are intended for observation, retrieval, analysis, and reporting.

  IMPORTANT:
    - “Read-only” does NOT mean “low risk”.
      Reads can still expose sensitive data, enable exfiltration, or trigger
      side-effects in some SaaS APIs (audit logs, notifications, rate limits).
    - Therefore, read-only tools are still governed by:
      permission gates, trust gates, privacy/data governance, and auditing.

  Template style:
    - YAML document
    - Jinja2 placeholders
    - Explicit allowlists, conservative defaults, strong redaction.

  Expected template inputs (recommended):
    tool_id: string (stable, snake_case)
    tool_name: string (human readable)
    tool_version: string (semver)
    tool_summary: string (one-liner)
    tool_description: string (longer description)
    owner: string
    contact: string
    entrypoint: string
    operations: list of objects (read operations)
    default_scopes: list[string]
    default_trust_min: string (e.g., "T1","T2","T3")
    tags: list[string]
    examples: list (optional)

============================================================================= #}

tool_spec_version: 1

tool:
  id: "{{ tool_id }}"
  name: "{{ tool_name }}"
  version: "{{ tool_version }}"
  risk_tier: "readonly"

  summary: "{{ tool_summary }}"
  description: |-
    {{ tool_description }}

  ownership:
    owner: "{{ owner }}"
    contact: "{{ contact }}"
    escalation:
      policy_doc: "docs/POLICIES.md"
      permission_doc: "docs/API_PERMISSIONS.md"
      trust_doc: "docs/TRUST_MODEL.md"
      privacy_doc: "config/policies/privacy.yaml"
      data_governance_doc: "config/policies/data_governance.yaml"
      web_access_doc: "docs/WEB_ACCESS.md"

  tags:
{% if tags and tags|length > 0 %}
{% for t in tags %}
    - "{{ t }}"
{% endfor %}
{% else %}
    - "readonly"
    - "governed"
    - "audited"
{% endif %}

  # ---------------------------------------------------------------------------
  # Execution wiring
  # ---------------------------------------------------------------------------
  execution:
    entrypoint: "{{ entrypoint }}"

    sandbox:
      enabled: true
      # Read-only tools often need network; keep it explicit and policy-gated.
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
            - "data/uploads/*"
            - "data/domains/*"
            - "data/knowledge_graph/*"
            - "data/web_knowledge/*"
            - "data/conversations/*"
{% endif %}
        write:
          # Read-only tools should not write except for local caches/artifacts
          # when explicitly allowed. Keep disabled by default.
          enabled: {{ fs_write_enabled | default(false) }}
          allowlist:
{% if fs_write_allowlist and fs_write_allowlist|length > 0 %}
{% for p in fs_write_allowlist %}
            - "{{ p }}"
{% endfor %}
{% else %}
            - "data/cache/*"
            - "data/artifacts/reports/*"
{% endif %}

    timeouts:
      tool_seconds: {{ tool_timeout_seconds | default(60) }}
      operation_seconds: {{ op_timeout_seconds | default(45) }}

    retries:
      enabled: true
      max_attempts: {{ max_attempts | default(3) }}
      backoff: "exponential"
      retry_on:
        - "transient_network_error"
        - "rate_limited"
        - "timeout"
      never_retry_on:
        - "validation_error"
        - "permission_denied"
        - "policy_blocked"

  # ---------------------------------------------------------------------------
  # Governance + security gates
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
      minimum_trust: "{{ default_trust_min | default('T1') }}"
      behavior: |-
        Even read-only access may be blocked if trust is too low for sensitive
        data classes or high-volume extraction patterns.

    safety_gate:
      enabled: true
      policy_ref:
        - "config/policies/privacy.yaml"
        - "config/policies/data_governance.yaml"
        - "config/policies/web_access.yaml"
        - "config/policies/offensive_security.yaml"
      behavior: |-
        The safety gate enforces privacy constraints, prevents exfil patterns,
        and blocks prohibited web domains/content categories.

  # ---------------------------------------------------------------------------
  # Telemetry, auditability, and redaction
  # ---------------------------------------------------------------------------
  telemetry:
    audit:
      enabled: true
      location: "data/logs/audit/"
      emit_events:
        - "tool.call.requested"
        - "tool.call.validated"
        - "tool.call.denied"
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
    metrics:
      enabled: true
      emit:
        - "latency_ms"
        - "success_rate"
        - "denial_rate"
        - "bytes_returned"
        - "records_returned"
        - "rate_limited_count"

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
    patterns:
      - "(?i)bearer\\s+[A-Za-z0-9\\-\\._~\\+\\/]+=*"
      - "(?i)eyJ[A-Za-z0-9_\\-]{10,}\\.[A-Za-z0-9_\\-]{10,}\\.[A-Za-z0-9_\\-]{10,}"   # JWT-ish

  # ---------------------------------------------------------------------------
  # Human-facing behavior contract
  # ---------------------------------------------------------------------------
  explainability:
    required: true
    must_include:
      - "what_will_be_read"
      - "why_this_is_allowed"
      - "which_policies_were_checked"
      - "which_scopes_and_delegations_were_used"
      - "data_classification_and_redactions"
      - "confidence_and_uncertainties"
    refusal_style: |-
      If denied, explain the missing scope/approval/policy constraint at a safe
      level and suggest a narrower query or additional approvals.

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

      risk_notes: |-
{% if op.risk_notes %}
        {{ op.risk_notes }}
{% else %}
        Potential risks include sensitive data exposure and high-volume extraction.
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
          - "read"

      limits:
        # Apply conservative defaults to reduce data exfiltration risk.
        max_items: {{ op.max_items | default(200) }}
        max_bytes: {{ op.max_bytes | default(2_000_000) }}  # ~2MB
        rate_limit:
          per_minute: {{ op.per_minute | default(60) }}

      caching:
        allowed: {{ op.caching_allowed | default(true) }}
        ttl_seconds: {{ op.cache_ttl_seconds | default(300) }}
        cache_location: "data/cache/"

      input_schema:
        type: object
        additionalProperties: false
        properties:
          query:
            type: string
            description: "User/agent query string. Must be validated/sanitized."
          filters:
            type: object
            additionalProperties: false
            description: "Structured filters (resource constraints)."
          limit:
            type: integer
            minimum: 1
            maximum: {{ op.max_items | default(200) }}
            default: {{ op.default_limit | default(50) }}
          cursor:
            type: string
            description: "Pagination cursor (opaque)."
        required:
          - "query"

      output_schema:
        type: object
        additionalProperties: false
        properties:
          request_id: { type: string }
          allowed: { type: boolean }
          redactions_applied:
            type: array
            items: { type: string }
          items:
            type: array
            items: { type: object }
          next_cursor:
            type: string
          warnings:
            type: array
            items: { type: string }
        required:
          - "request_id"
          - "allowed"
          - "items"

{% endfor %}
{% else %}
    - id: "REPLACE_ME"
      summary: "Replace with a concrete read operation"
      description: |-
        Define at least one read operation with explicit schemas and limits.

      permissions:
        required_scopes:
          - "REQUIRE_SCOPES"
        methods:
          - "read"

      limits:
        max_items: 200
        max_bytes: 2000000
        rate_limit:
          per_minute: 60

      caching:
        allowed: true
        ttl_seconds: 300
        cache_location: "data/cache/"

      input_schema:
        type: object
        additionalProperties: false
        properties:
          query: { type: string }
          limit: { type: integer, minimum: 1, maximum: 200, default: 50 }
        required: ["query"]

      output_schema:
        type: object
        additionalProperties: false
        properties:
          request_id: { type: string }
          allowed: { type: boolean }
          items: { type: array, items: { type: object } }
          next_cursor: { type: string }
        required: ["request_id", "allowed", "items"]
{% endif %}

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
    - name: "basic_query"
      description: "A basic read query with a safe limit"
      operation_id: "REPLACE_ME"
      input:
        query: "status:open"
        limit: 25
{% endif %}
