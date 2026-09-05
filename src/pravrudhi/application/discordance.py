"""Compare binary outcomes paired by held-out item and sampling seed.

Concordant pairs contribute zero to the difference: only candidate wins and
losses carry information about its direction. Conditioning on these discordant
pairs gives an exact binomial McNemar test and an exact confidence interval for
their win/loss odds. Concordant items still enter the pass-rate denominator.
"""

from dataclasses import dataclass
from math import comb, exp, fsum, inf, log, log1p


@dataclass(frozen=True)
class Discordance:
    n: int
    concordant: int
    wins: int
    losses: int
    delta: float
    p_mcnemar: float
    or_lower: float
    or_upper: float


def _lower_proportion(successes: int, total: int) -> float:
    """Invert P(Binomial(total, p) >= successes) = 0.025 by bisection."""
    if successes == 0:
        return 0.0
    # Log probabilities avoid overflow in large binomial coefficients and
    # premature underflow from separately computing powers of p and (1-p).
    coefficients = [(k, log(comb(total, k))) for k in range(successes, total + 1)]
    low, high = 0.0, 1.0
    for _ in range(64):
        p = (low + high) / 2.0
        if p in (low, high):
            break
        tail = fsum(exp(c + k * log(p) + (total - k) * log1p(-p)) for k, c in coefficients)
        if tail < 0.025:
            low = p
        else:
            high = p
    return (low + high) / 2.0


def discordance(incumbent: dict[str, int], candidate: dict[str, int]) -> Discordance:
    """Summarize shared binary scores; define delta as zero if none overlap.

    The 95% odds interval transforms equal-tailed Clopper-Pearson limits.
    Inputs are assumed to contain only 0 (failed) and 1 (passed).
    """
    shared = incumbent.keys() & candidate.keys()
    n = len(shared)
    wins = sum(candidate[item] == 1 and incumbent[item] == 0 for item in shared)
    losses = sum(candidate[item] == 0 and incumbent[item] == 1 for item in shared)
    total = wins + losses
    if total == 0:
        return Discordance(n, n, 0, 0, 0.0, 1.0, 0.0, inf)

    # Integer summation and division avoid converting 2**total to a float.
    p_mcnemar = min(1.0, 2 * sum(comb(total, k) for k in range(min(wins, losses) + 1)) / (1 << total))
    lower = _lower_proportion(wins, total)
    reverse_lower = _lower_proportion(losses, total)
    or_lower = lower / (1.0 - lower)
    # The upper proportion is 1 - reverse_lower. Transform directly to avoid
    # rounding a proportion near one to one before calculating its odds.
    or_upper = (1.0 - reverse_lower) / reverse_lower if losses else inf
    return Discordance(n, n - total, wins, losses, (wins - losses) / n, p_mcnemar, or_lower, or_upper)
