# Mode Contracts & Validation Semantics

This document defines **mode-specific contracts** for generation, validation, and export behavior.
It is intentionally explicit to avoid accidental behavior regressions while improving reliability.

---

## 1) Core Principle

CAISSA uses **mode-aware correctness**:

- Be strict where output is expected to be final.
- Be permissive where the workflow naturally includes incomplete/forfeit states.

This avoids over-normalizing fundamentally different workflows.

---

## 2) Single Game (One LLM)

### Purpose
Generate a complete, standalone game artifact from one LLM response pipeline.

### Validation Contract
- PGN must be extractable.
- Movetext must contain legal SAN moves.
- Result must be **terminal**:
  - `1-0`, `0-1`, or `1/2-1/2`
- Result `*` is treated as incomplete and rejected.

### Retry Behavior
- On extraction, legality, or terminal-result failure: retry with corrective feedback.
- If retries exhausted: generation is reported failed.

### Export Contract
- Exports are produced only for successful finalized games.
- `all` format writes multi-artifacts (`.pgn`, `.md`, `.html`, `.json`).

---

## 3) Batch Mode (One LLM, Multiple Games)

### Purpose
Generate many standalone games under a shared batch configuration.

### Validation Contract
- Each game is validated independently.
- Legality is required per game.
- Non-terminal/incomplete results are treated as failures by generator policy.

### Export Contract
- Per-game exports follow requested formats.
- Batch summary files are generated (markdown/json).

---

## 4) LLM vs LLM Match (Single Match)

### Purpose
Run a live two-player match where move generation is iterative by turn.

### Validation Contract
- Move-level validation is enforced per turn.
- Retry limits exist per move/player.
- Forfeit is a valid terminal state.

### Result Semantics
- A match may terminate by:
  - checkmate/stalemate/insufficient/fifty-move/threefold/fivefold
  - resignation/timeout/forfeit/max-moves/adjudication

### Export Contract
- Export is allowed for exportable matches with move history.
- If no moves exist, export is skipped by design.

---

## 5) Tournament Mode

### Purpose
Aggregate multiple matches across a competition format.

### Validation Contract
- Match-level semantics carry through (including forfeit/timeout).
- Tournament validity does not require every game to be decisive.

### Export Contract
- Tournament-level artifacts: standings/crosstable/report/json.
- Per-game artifacts depend on chosen export mode/settings.

---

## 6) Commentary & Annotation Semantics

### Sources
- Inline PGN comments (`{...}`)
- NAG markers (`!`, `!!`, `?`, etc.)
- Dedicated commentary sections (when emitted by generator/export style)

### Contract
- Parser attempts to preserve/marshal commentary into structured move annotations.
- Export formats may represent annotations differently (inline vs sectioned),
  but should not silently drop available annotation intent.

---

## 7) Export Guardrail (Warning-Only)

CAISSA supports a post-export consistency guardrail in warning mode:

- Compare available outputs (e.g., PGN vs JSON) for obvious mismatches.
- Log/report issues for operator visibility.
- Do **not** hard-fail current run in warning mode.

This is intentionally non-blocking to avoid production disruption.

---

## 8) Prompt Studio Contract

Prompt Studio provides controlled prompt transparency/customization:

- View active prompt catalog.
- Session overrides without mutating built-ins.
- Optional profile save/load in custom profile directory.
- Built-in prompts remain the canonical fallback.

---

## 9) Troubleshooting by Symptom

### Symptom: “Game in progress” (`*`) in single-game output
- Expected behavior now: rejected during generation retries.
- If observed in artifacts, check whether output came from legacy/manual path.

### Symptom: Match with no exported file
- In LLM-vs-LLM, no-move match is intentionally non-exportable.
- Check termination reason and retry/forfeit logs.

### Symptom: Annotation count differs across formats
- Some representational variance is expected.
- Verify parser logs and export guardrail warnings for actual data-loss indicators.

---

## 10) Change Safety Rules

When modifying validation/export behavior:

1. Preserve mode contracts above.
2. Add tests before changing strictness defaults.
3. Introduce strict checks as opt-in first when uncertainty exists.
4. Prefer warnings + observability before hard enforcement.

