---
name: generalized-bugfix
description: Use when fixing bugs, regressions, bad model outputs, parsing errors, data contract issues, or unexpected behavior where a single failing case may represent a broader class of problems. Requires root-cause analysis, class-level generalization, broad tests, and documentation before implementing a fix.
---

# Generalized Bugfix

## Core Rule

Do not fix only the single reported case.

Every bugfix must first answer:

```text
This specific failure is an example of what broader class of problem?
```

Fix the class of problem when reasonable. Use the reported case as a regression test or few-shot example, not as the whole solution.

## When To Use

Use this skill for:

- A user-visible bug.
- A test failure.
- A bad LLM structured output.
- Unit conversion, normalization, parsing, or schema mistakes.
- API contract mismatches.
- Route planning, scoring, filtering, or ranking surprises.
- Any issue where a one-line conditional would only patch the current example.

## Workflow

### 1. Locate The Failing Layer

Identify which layer first produced the bad value or behavior:

- User input understanding.
- LLM prompt or structured output.
- Normalization or validation.
- State merge.
- Service or strategy logic.
- External API adapter.
- Frontend rendering.

Do not fix downstream symptoms if the bad value originates upstream.

### 2. Generalize The Bug

State the broader class in one sentence.

Good:

```text
The system does not reliably normalize natural-language units into standard schema units.
```

Bad:

```text
"一天" became 1 hour.
```

### 3. Design A Class-Level Fix

Prefer a reusable rule, module, prompt contract, schema validation, or normalizer.

Examples:

- Add a unit normalization layer for all time, budget, distance, queue, and people-count fields.
- Add schema-level validation for impossible or suspicious values.
- Add prompt instructions requiring standard output units.
- Add adapter-level normalization for external API responses.

Avoid fixes that only match one phrase unless that phrase is added as a regression example for a broader rule.

### 4. Add Broad Tests

Tests must include:

- The reported failing case.
- At least two sibling cases from the same class, when possible.
- A negative case that should not be changed.

For LLM extraction or unit conversion, cover related variants:

```text
一天 / 一日游 / 1天
半天 / 半日游
2天
下午两点
半小时
人均200
总预算400，两个人
```

### 5. Update Documentation When The Contract Changes

If the fix changes a shared contract, document it:

- Prompt contract.
- API contract.
- Route field contract.
- Version log.
- Team engineering rule.

### 6. Verify End To End

Run the smallest test that proves the regression, then a broader verification command.

Do not claim the bug is fixed until verification has run in the current session.

## Required Output Summary

When reporting the fix, include:

- Root cause layer.
- Broader bug class.
- Generalized fix.
- Tests added.
- Remaining risk.

## Example

Reported bug:

```text
User says "改成上海两个人一天", but route has only one stop.
```

Do not only add:

```text
if message contains "一天": duration_hours = 8
```

Instead:

```text
Root class: natural-language units are not consistently normalized into schema standard units.
General fix: prompt standard-unit contract + unit normalizer + tests for day, half-day, hours, minutes, total budget, per-person budget, and time-of-day.
```
