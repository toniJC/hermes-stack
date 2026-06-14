## Section 12 — BMAD Model Assignment Table

INFORMATIONAL ONLY. Real routing lives in `schema-service/app/registry.py`. If this table and `registry.py` disagree, `registry.py` wins.

| Phase | LiteLLM Alias | Endpoint |
|-------|--------------|---------|
| bmad-analyze | local-thinking | :8001 |
| bmad-prd | local-thinking | :8001 |
| bmad-ux | local-hermes | :8006 |
| bmad-architect | local-thinking | :8001 |
| bmad-stories | local-coder | :8000 |

---

## Section 13 — BMAD Dependency Graph + UX Skip Rule

### Dependency Graph

```
analyze → prd → architect → stories → (SDD) propose → …
               ↘ ux ↗
```

- `analyze` starts from a raw idea or brief — no prerequisite artifact.
- `prd` requires `analyze`.
- `ux` requires `prd`. **OPTIONAL phase** — see UX Skip Rule below.
- `architect` requires `prd`; consumes `ux` if present (pass as optional field).
- `stories` requires `prd` + `architect`.

### UX Skip Rule

- **MANDATORY** for changes that involve user-facing UI, interaction design, or any screen/flow.
- **SKIPPABLE** for pure backend, API-only, infra, or data-pipeline changes with no user-facing component.
- When skipping: proceed directly from `prd` → `architect`. Do NOT pass a `ux` field to the architect endpoint.
- HALT if a required prerequisite artifact is absent from Engram.

---

## Section 14 — BMAD Endpoints

Base URL: `http://localhost:8010`

| Phase | Endpoint | Required | Optional | Produces |
|-------|----------|---------|---------|---------|
| analyze | POST /v1/bmad/analyze | `context` | — | problem/users/goals |
| prd | POST /v1/bmad/prd | `context` | `analyze` (raw JSON) | requirements PRD |
| ux | POST /v1/bmad/ux | `context` | `prd` (raw JSON) | flows/screens |
| architect | POST /v1/bmad/architect | `context` | `prd` (raw JSON), `ux` (raw JSON) | architecture |
| stories | POST /v1/bmad/stories | `context` | `prd` (raw JSON), `architect` (raw JSON) | epic + stories |

Every successful response includes `_meta.phase` and `_meta.worker` (same as SDD phases). Same `X-SDD-Phase` / `X-SDD-Worker` headers apply.

---

## Section 15 — BMAD Topic Keys

| Artifact | topic_key |
|----------|-----------|
| Analysis | `bmad/{change}/analyze` |
| PRD | `bmad/{change}/prd` |
| UX | `bmad/{change}/ux` |
| Architecture | `bmad/{change}/architect` |
| Stories | `bmad/{change}/stories` |

Same save protocol as SDD: capture `$RESPONSE` raw, `mem_save` with `capture_prompt: false`, preserve `_meta` intact.

Always pass `project: "$HERMES_PROJECT"` explicitly with every MCP call.

---

## Section 16 — BMAD Phase Flow

For each BMAD phase, follow this 7-step loop:

1. Retrieve prerequisite artifacts from Engram:
   ```bash
   # Example: retrieve prd artifact before calling architect
   mem_search(query: "bmad/{change}/prd", project: "$HERMES_PROJECT") → get ID
   mem_get_observation(id: <ID>) → full content → store in $PRD
   ```
2. POST to the Schema Service endpoint with enriched context:
   ```bash
   RESPONSE=$(curl -s -X POST http://localhost:8010/v1/bmad/<phase> \
     -H "Content-Type: application/json" \
     -d "$PAYLOAD")
   ```
3. Capture `$RESPONSE` raw in a shell variable BEFORE any other operation.
4. Show raw response to the user.
5. Save to Engram:
   ```
   mem_save(
     title: "{phase}: {change}",
     topic_key: "bmad/{change}/{phase}",
     type: "architecture",
     project: "$HERMES_PROJECT",
     capture_prompt: false,
     content: ($RESPONSE | tostring)
   )
   ```
6. Ask user to confirm before proceeding (required after: `analyze`, `prd`, `architect`, `stories`).
7. On confirm, proceed to the next dependent phase.

### Payload assembly with jq (safe — no direct interpolation)

```bash
# Single field
PAYLOAD=$(jq -n --arg ctx "$CONTEXT" '{context: $ctx}')

# With optional upstream artifact
PAYLOAD=$(jq -n \
  --arg ctx "$CONTEXT" \
  --argjson analyze "$ANALYZE_RESPONSE" \
  '{context: $ctx, analyze: ($analyze | tostring)}')
```

Rules — never break these:
- ALWAYS use `jq -n --argjson` when folding a prior `$RESPONSE` into a new payload.
- NEVER interpolate `$RESPONSE` directly into a JSON string — shell escaping will corrupt or drop `_meta`.
- If a Schema Service call fails or returns non-2xx: STOP, report the exact HTTP status, do NOT save a partial result.

---

## Section 17 — BMAD → SDD Handoff

After `stories` is saved and the user confirms, assemble the SDD propose payload by pulling the 3 BMAD artifacts from Engram and folding them into the bridge fields on `ProposeIn`.

```bash
# Step 1 — retrieve BMAD artifacts from Engram (mem_search + mem_get_observation each)
# PRD_ID=$(mem_search bmad/{change}/prd) → mem_get_observation(PRD_ID) → $PRD
# ARCH_ID=$(mem_search bmad/{change}/architect) → mem_get_observation(ARCH_ID) → $ARCH
# STORIES_ID=$(mem_search bmad/{change}/stories) → mem_get_observation(STORIES_ID) → $STORIES

# Step 2 — assemble propose payload
PAYLOAD=$(jq -n \
  --arg ctx "BMAD planning complete for {change}" \
  --argjson prd "$PRD" \
  --argjson arch "$ARCH" \
  --argjson stories "$STORIES" \
  '{
    context: $ctx,
    bmad_prd: ($prd | tostring),
    bmad_architect: ($arch | tostring),
    bmad_stories: ($stories | tostring)
  }')

# Step 3 — call SDD propose
RESPONSE=$(curl -s -X POST http://localhost:8010/v1/sdd/propose \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

echo "$RESPONSE"

# Step 4 — save to Engram and continue with normal SDD flow
# mem_save topic_key: sdd/{change}/proposal
# Then: spec → design → tasks → apply → verify
```

Notes:
- `bmad_prd`, `bmad_architect`, and `bmad_stories` are individually optional on `ProposeIn`. If a BMAD phase was skipped (e.g. `ux`), simply omit it — it has no bridge field in `ProposeIn` anyway.
- The `ux` artifact is consumed by `architect` inline and does not need its own bridge field in `ProposeIn`.
- After the handoff, continue with the standard SDD flow: `spec → design → tasks → apply → verify → archive`.
