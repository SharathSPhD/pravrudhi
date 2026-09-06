import pytest

from pravrudhi.application.delegate import TaskSpec
from pravrudhi.application.sandbox_policy import (
    Policy,
    SandboxPolicyError,
    apply_policy,
    load_policies,
    policy_for,
)


def test_packaged_policies_declare_proposal_selfbuild_review() -> None:
    policies = load_policies()
    assert set(policies) == {"proposal", "selfbuild", "review"}
    for policy in policies.values():
        assert policy.network in ("none", "provider-only", "open")


def test_denied_paths_always_include_the_protected_directories() -> None:
    policy = Policy(
        id="custom",
        allowed_paths=("anything/**",),
        denied_paths=(),
        network="none",
        tools=(),
        max_wall_s=60,
        validate="true",
    )
    for protected in ("pravrudhi_kernel/**", "research/**", "gates/**", ".pravrudhi/**"):
        assert protected in policy.denied_paths


def test_denied_always_wins_over_allowed() -> None:
    policy = Policy(
        id="wide-open",
        allowed_paths=("**",),
        denied_paths=(),
        network="none",
        tools=(),
        max_wall_s=60,
        validate="true",
    )
    spec = TaskSpec(
        task_id="t1",
        prompt="do the thing",
        allowed_paths=("pravrudhi_kernel/foo.py", "research/notes.md", "src/pravrudhi/ok.py"),
    )
    narrowed = apply_policy(spec, policy)
    assert narrowed.allowed_paths == ("src/pravrudhi/ok.py",)


def test_review_policy_yields_no_writable_path() -> None:
    review = policy_for("review")
    assert review.allowed_paths == ()
    spec = TaskSpec(
        task_id="t2",
        prompt="look but do not touch",
        allowed_paths=("src/pravrudhi/**", "tests/**"),
    )
    narrowed = apply_policy(spec, review)
    assert narrowed.allowed_paths == ()


def test_prompt_names_the_policy() -> None:
    policy = policy_for("proposal")
    spec = TaskSpec(
        task_id="t3",
        prompt="original prompt",
        allowed_paths=("proposals/obj/step/*",),
    )
    narrowed = apply_policy(spec, policy)
    assert "original prompt" in narrowed.prompt
    assert f"Sandbox policy {policy.id!r}" in narrowed.prompt


def test_apply_policy_sets_validate_and_timeout_from_policy() -> None:
    policy = policy_for("selfbuild")
    spec = TaskSpec(
        task_id="t4",
        prompt="build it",
        allowed_paths=("src/pravrudhi/foo.py",),
        validate="echo unused",
        timeout_s=1,
    )
    narrowed = apply_policy(spec, policy)
    assert narrowed.validate == policy.validate
    assert narrowed.timeout_s == policy.max_wall_s


def test_unknown_policy_kind_raises() -> None:
    with pytest.raises(SandboxPolicyError):
        policy_for("does-not-exist")
