# MERIDIAN Exact Remediation Review

Date: 2026-07-14

- ARGUS `683134a7cccd6b4dd1b1cd1604d2641615f07307`: the v2 producer plus
  conservative v1 reader is an in-place schema evolution and needs no ADR, but
  later VERA/SENTINEL composition findings still block promotion.
- FORGE `cd9cd50422115761a2340e3d322b449516f85b0d`: provision/isolation lineage
  composes, but safe-delta duplicates the isolation-owned containment/junction
  guard. `CR-DEC-0012` authorizes a narrow canonical guarded-subpath API. No ADR
  is required while trust and tenancy assumptions remain unchanged.

Review was static and read-only.
