"""Deriving the visible checks a harness may select on, from the problem statement alone.

The harness track's whole premise is that a scaffold can make a fixed model write correct code more often — by
retrying against feedback, by drawing several samples and keeping the one that passes, by asking the model to check
its own work. Every one of those needs something to check against, and the executor looked only for `assert ` lines.
MBPP+ prompts carry one, so those strategies worked there. HumanEval prompts carry none: their examples live in the
docstring as `>>>` doctests. So on HumanEval every selection strategy was a silent no-op — retry never retried,
best-of-n always kept the first sample — and the only axis the harness could vary was the prompt. An entire branch
of the grammar could not move the score, which is half the reason the track has never beaten its baseline.

This turns those doctest examples into the same kind of check an `assert` line already is, conservatively: a line is
turned into a check only when the expected value is a single line that parses as a Python literal. Anything
uncertain -- a multi-line expected value, an expected exception, a call whose result is not a literal -- is left
out rather than turned into a check that might penalise correct code. Hidden tests never appear here; these are
only the examples the problem itself already shows the solver.
"""

from __future__ import annotations

import ast


def _is_literal(text: str) -> bool:
    """Whether `text` is a single Python literal expression (number, string, bool, None, list, dict, tuple, set).

    A check is only emitted when the expected side is one of these, so `assert <call> == <expected>` cannot itself
    raise for a reason unrelated to the candidate's correctness."""
    try:
        ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return False
    return True


def doctest_checks(question: str) -> list[str]:
    """`assert` checks derived from `>>>` doctest examples in the prompt's docstring."""
    lines = question.splitlines()
    checks: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith(">>>"):
            call = stripped[3:].strip()
            expected_parts: list[str] = []
            j = i + 1
            # The expected value ends at the next prompt, a blank line, the end of the docstring, or code.
            while j < len(lines):
                nxt = lines[j].strip()
                if nxt.startswith(">>>") or nxt == "" or '"""' in nxt or "'''" in nxt:
                    break
                expected_parts.append(nxt)
                j += 1
            i = j
            if not call or call.endswith((":", "\\")) or "=" in call.split("(")[0]:
                continue  # a statement or an assignment, not an expression that yields a value
            expected = " ".join(expected_parts)
            if not expected or expected.startswith("Traceback") or not _is_literal(expected):
                continue
            checks.append(f"assert ({call}) == ({expected})")
        else:
            i += 1
    return checks


def visible_tests(question: str, *, use: bool = True) -> list[str]:
    """Every check the harness is allowed to select on for this problem: the explicit `assert ` lines an MBPP+
    prompt carries, plus the checks derived from any `>>>` doctest examples a HumanEval prompt carries. De-duplicated
    and order-preserving."""
    if not use:
        return []
    found = [line.strip() for line in question.splitlines() if line.strip().startswith("assert ")]
    found += doctest_checks(question)
    seen: set[str] = set()
    out: list[str] = []
    for t in found:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out
