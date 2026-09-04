import json
import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pravrudhi_kernel.ledger.jcs import canonicalize


@pytest.mark.parametrize(
    ("obj", "want"),
    [
        ({"b": 1, "a": 2}, '{"a":2,"b":1}'),
        ([1.0, 2.5, 1e-7, 1e21, 123456789012345680000.0], "[1,2.5,1e-7,1e+21,123456789012345680000]"),
        ({"s": "é\n\x1f"}, '{"s":"é\\n\\u001f"}'),
        ({"n": None, "t": True, "f": False}, '{"f":false,"n":null,"t":true}'),
        ({"é": 1, "z": 2, "a": 3}, '{"a":3,"z":2,"é":1}'),
        (0.1, "0.1"),
        (-0.0, "0"),
        (1e-6, "0.000001"),
        (1.5e300, "1.5e+300"),
        (5e-324, "5e-324"),
    ],
)
def test_known_vectors(obj: object, want: str) -> None:
    assert canonicalize(obj) == want


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), {"x": float("-inf")}])
def test_non_finite_refused(bad: object) -> None:
    with pytest.raises(ValueError):
        canonicalize(bad)


@given(
    st.dictionaries(
        st.text(min_size=1),
        st.one_of(
            st.integers(),
            st.floats(allow_nan=False, allow_infinity=False),
            st.text(),
            st.booleans(),
            st.none(),
        ),
    )
)
def test_prop_canonical_is_idempotent_order_free_and_round_trips(d: dict[str, object]) -> None:
    a = canonicalize(d)
    b = canonicalize(dict(reversed(list(d.items()))))
    assert a == b
    back = json.loads(a)
    for k, v in d.items():
        if isinstance(v, float):
            assert back[k] == v or math.isclose(back[k], v, rel_tol=1e-15)
        else:
            assert back[k] == v
