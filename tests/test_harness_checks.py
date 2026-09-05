"""The harness may only select on checks derived from the problem statement, and on HumanEval those are doctests.

Reading only `assert ` lines made retry, best-of-n and feedback silent no-ops on HumanEval, where the examples live
in the docstring as `>>>` doctests. That is half the reason the harness track has never beaten its baseline: an
entire branch of the grammar could not move the score. These tests pin the extractor that unlocks it.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "docker" / "jobs"))

from checks import doctest_checks, visible_tests  # noqa: E402


def test_humaneval_doctest_becomes_a_check() -> None:
    prompt = (
        'def has_close(numbers, threshold):\n'
        '    """ True if two numbers are closer than threshold.\n'
        '    >>> has_close([1.0, 2.0, 3.0], 0.5)\n'
        '    False\n'
        '    >>> has_close([1.0, 2.8, 3.0], 0.3)\n'
        '    True\n'
        '    """\n'
    )
    got = visible_tests(prompt)
    assert "assert (has_close([1.0, 2.0, 3.0], 0.5)) == (False)" in got
    assert "assert (has_close([1.0, 2.8, 3.0], 0.3)) == (True)" in got


def test_mbpp_assert_line_is_kept() -> None:
    assert visible_tests("Write add.\nassert add(2, 3) == 5") == ["assert add(2, 3) == 5"]


def test_asserts_and_doctests_combine_without_duplicates() -> None:
    prompt = 'def f(x):\n    """\n    >>> f(1)\n    2\n    """\nassert f(1) == 2\n'
    got = visible_tests(prompt)
    assert "assert f(1) == 2" in got
    assert "assert (f(1)) == (2)" in got
    assert len(got) == len(set(got))


def test_an_expected_exception_is_not_turned_into_a_check() -> None:
    prompt = 'def g(x):\n    """\n    >>> g(-1)\n    Traceback (most recent call last):\n    ValueError\n    """\n'
    assert doctest_checks(prompt) == []


def test_a_non_literal_expected_value_is_skipped() -> None:
    """`f(2)` -> `some_object()` is not a literal, so no check is emitted rather than one that might penalise
    correct code for an unrelated reason."""
    prompt = 'def f(x):\n    """\n    >>> f(2)\n    some_object()\n    """\n'
    assert doctest_checks(prompt) == []


def test_the_closing_docstring_quote_is_not_swallowed() -> None:
    prompt = 'def f(x):\n    """\n    >>> f(3)\n    [1, 2, 3]\n    """\n'
    assert doctest_checks(prompt) == ["assert (f(3)) == ([1, 2, 3])"]


def test_use_flag_disables_all_checks() -> None:
    assert visible_tests("assert add(1, 1) == 2", use=False) == []
