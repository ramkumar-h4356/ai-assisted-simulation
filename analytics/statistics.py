"""Pure-Python Student-t, Welch, effect-size and multiplicity calculations."""

from __future__ import annotations

from math import exp, lgamma, log, pi, sqrt


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    max_iterations = 200
    epsilon = 3e-14
    floor = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < floor:
        d = floor
    d = 1.0 / d
    h = d
    for m in range(1, max_iterations + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < floor:
            d = floor
        c = 1.0 + aa / c
        if abs(c) < floor:
            c = floor
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < floor:
            d = floor
        c = 1.0 + aa / c
        if abs(c) < floor:
            c = floor
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < epsilon:
            return h
    raise ArithmeticError("incomplete beta continued fraction did not converge")


def regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    if not 0.0 <= x <= 1.0 or a <= 0.0 or b <= 0.0:
        raise ValueError("regularized beta arguments are outside their domain")
    if x in {0.0, 1.0}:
        return x
    log_bt = lgamma(a + b) - lgamma(a) - lgamma(b) + a * log(x) + b * log1p_neg(x)
    bt = exp(log_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _beta_continued_fraction(a, b, x) / a
    return 1.0 - bt * _beta_continued_fraction(b, a, 1.0 - x) / b


def log1p_neg(x: float) -> float:
    # log(1-x) is stable enough in the branch used here (x is strictly below 1).
    from math import log1p
    return log1p(-x)


def student_t_cdf(value: float, degrees_freedom: float) -> float:
    if degrees_freedom <= 0.0:
        raise ValueError("degrees_freedom must be positive")
    if value == 0.0:
        return 0.5
    x = degrees_freedom / (degrees_freedom + value * value)
    tail = 0.5 * regularized_incomplete_beta(x, degrees_freedom / 2.0, 0.5)
    return 1.0 - tail if value > 0 else tail


def student_t_critical(probability: float, degrees_freedom: float) -> float:
    """Return the t quantile for probability in (0,1) by monotonic bisection."""
    if not 0.5 < probability < 1.0 or degrees_freedom <= 0:
        raise ValueError("invalid t quantile arguments")
    low, high = 0.0, 1.0
    while student_t_cdf(high, degrees_freedom) < probability:
        high *= 2.0
        if high > 1e6:
            raise ArithmeticError("could not bracket Student-t quantile")
    for _ in range(100):
        mid = (low + high) / 2.0
        if student_t_cdf(mid, degrees_freedom) < probability:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def mean_confidence_interval(mean: float, sample_stddev: float | None, sample_size: int, confidence_level: float) -> tuple[float, float] | None:
    if sample_size < 2 or sample_stddev is None:
        return None
    alpha = 1.0 - confidence_level
    critical = student_t_critical(1.0 - alpha / 2.0, sample_size - 1)
    margin = critical * sample_stddev / sqrt(sample_size)
    return mean - margin, mean + margin


def welch_comparison(
    mean_a: float,
    std_a: float,
    n_a: int,
    mean_b: float,
    std_b: float,
    n_b: int,
    confidence_level: float,
) -> dict[str, float] | None:
    """Compare independent groups using Welch's unequal-variance t method.

    Standard deviations must be sample standard deviations. Returns None when
    variance cannot be estimated (for example, both groups are constant).
    """
    if n_a < 2 or n_b < 2:
        return None
    variance_a = std_a * std_a
    variance_b = std_b * std_b
    term_a = variance_a / n_a
    term_b = variance_b / n_b
    standard_error = sqrt(term_a + term_b)
    if standard_error == 0.0:
        return None
    degrees = (term_a + term_b) ** 2 / (
        (term_a * term_a) / (n_a - 1) + (term_b * term_b) / (n_b - 1)
    )
    if degrees <= 0.0:
        return None
    difference = mean_b - mean_a
    t_value = difference / standard_error
    p_value = min(1.0, max(0.0, 2.0 * (1.0 - student_t_cdf(abs(t_value), degrees))))
    critical = student_t_critical((1.0 + confidence_level) / 2.0, degrees)
    margin = critical * standard_error
    pooled_denom = n_a + n_b - 2
    pooled_variance = (((n_a - 1) * variance_a) + ((n_b - 1) * variance_b)) / pooled_denom
    hedges_g = None
    if pooled_variance > 0.0:
        pooled_std = sqrt(pooled_variance)
        cohen_d = difference / pooled_std
        correction = 1.0 - (3.0 / (4.0 * (n_a + n_b) - 9.0))
        hedges_g = correction * cohen_d
    return {
        "mean_difference": difference,
        "welch_t": t_value,
        "degrees_freedom": degrees,
        "p_value": p_value,
        "confidence_lower": difference - margin,
        "confidence_upper": difference + margin,
        "hedges_g": hedges_g,
    }


def holm_adjust(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values in the original input order."""
    count = len(p_values)
    order = sorted(range(count), key=lambda index: p_values[index])
    adjusted = [0.0] * count
    running = 0.0
    for rank, original_index in enumerate(order):
        candidate = min(1.0, (count - rank) * p_values[original_index])
        running = max(running, candidate)
        adjusted[original_index] = running
    return adjusted


def effect_magnitude(hedges_g: float | None) -> str:
    if hedges_g is None:
        return "not_estimable"
    magnitude = abs(hedges_g)
    if magnitude < 0.2:
        return "negligible"
    if magnitude < 0.5:
        return "small"
    if magnitude < 0.8:
        return "medium"
    return "large"
