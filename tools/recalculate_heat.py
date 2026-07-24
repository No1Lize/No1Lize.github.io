from dataclasses import dataclass


@dataclass(frozen=True)
class HeatInputs:
    funding: float
    leading_institutions: float
    important_events: float
    ipo: float
    research_policy: float


def heat_score(inputs: HeatInputs) -> float:
    values = (
        inputs.funding,
        inputs.leading_institutions,
        inputs.important_events,
        inputs.ipo,
        inputs.research_policy,
    )
    if any(value < 0 or value > 100 for value in values):
        raise ValueError("All normalized indicators must be in [0, 100]")
    return round(
        0.30 * inputs.funding
        + 0.20 * inputs.leading_institutions
        + 0.20 * inputs.important_events
        + 0.15 * inputs.ipo
        + 0.15 * inputs.research_policy,
        2,
    )
