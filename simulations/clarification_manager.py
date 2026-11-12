"""Manage questions generated from scenario validation findings."""

from dataclasses import dataclass

from simulations.requirements import (
    RequirementStatus,
    ValidationReport,
)


@dataclass(frozen=True, slots=True)
class ClarificationQuestion:
    """Represent one question that needs a user response."""

    path: str
    status: RequirementStatus
    question: str


def _question_for(path: str, status: RequirementStatus) -> str:
    """Generate a user-facing question for a validation path."""

    if path == "resources":
        return (
            "Which resources are involved? Provide each resource's "
            "name and capacity. Mention all resources."
        )

    if path == "jobs":
        return (
            "Which jobs or entities enter the system? Provide their "
            "identifiers, arrival times, and service stages."
        )

    if path == "scenario.name":
        return "What descriptive name should be given to this scenario?"

    if path.endswith(".name"):
        return "Provide a non-empty, unique name for this resource."

    if path.endswith(".entity_id"):
        return "Provide a non-empty, unique identifier for this job."

    if path.endswith(".capacity"):
        return "What is this resource's capacity? Provide a positive integer."

    if path.endswith(".arrival_time"):
        return (
            "At what simulation time does this entity arrive? "
            "Provide a finite, non-negative number."
        )

    if path.endswith(".stages") or path == "stages":
        return (
            "Describe at least one service stage for this job. "
            "For each stage, provide its resource and service duration."
        )

    if path.endswith(".service_duration"):
        return (
            "How long does this service stage take? "
            "Provide a finite, non-negative number."
        )

    if path.endswith(".resource_name"):
        return (
            "Which defined resource performs this service stage? "
            "Use the exact resource name."
        )

    if path.endswith(".resource_reference"):
        return (
            "This stage refers to a resource that does not exist. "
            "Should the resource be added, or should the stage use "
            "an existing resource?"
        )

    return (
        f"Please clarify '{path}'. "
        "Provide the missing or corrected simulation information."
    )


def build_clarification_questions(
    report: ValidationReport,
) -> tuple[ClarificationQuestion, ...]:
    """Build a deduplicated list of questions from validation findings."""

    questions: dict[str, ClarificationQuestion] = {}

    actionable_statuses = {
        RequirementStatus.MISSING,
        RequirementStatus.INVALID,
        RequirementStatus.NEEDS_CLARIFICATION,
    }

    for result in report.results:
        if result.status not in actionable_statuses:
            continue

        path = result.path

        question = ClarificationQuestion(
            path=path,
            status=result.status,
            question=_question_for(path, result.status),
        )

        existing = questions.get(path)

        # Prefer clarification or invalidity over a simple missing result.
        if (
            existing is None
            or result.status in {
                RequirementStatus.INVALID,
                RequirementStatus.NEEDS_CLARIFICATION,
            }
        ):
            questions[path] = question

    return tuple(questions.values())
def merge_model_data(
    previous: dict,
    revised: dict,
) -> dict:
    """Preserve established information when merging a revised model."""

    if not isinstance(previous, dict) or not isinstance(revised, dict):
        raise TypeError("Both model versions must be dictionaries")

    def merge(old, new):
        if new is None:
            return old

        if isinstance(old, dict) and isinstance(new, dict):
            merged = dict(old)

            for key, value in new.items():
                merged[key] = merge(old.get(key), value)

            return merged

        if isinstance(old, list) and isinstance(new, list):
            if len(old) == len(new):
                return [
                    merge(old_item, new_item)
                    for old_item, new_item in zip(old, new)
                ]

            return new

        return new

    return merge(previous, revised)