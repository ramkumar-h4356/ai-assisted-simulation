from copy import deepcopy


BASE_DRAFT = {
    "title": "Community resource sharing idea",
    "working_statement": "A community coordinates access to a shared resource.",
    "summary": "Members coordinate and share a resource under rules that are not yet fully defined.",
    "concepts": [
        {
            "name": "Community member", "kind": "actor",
            "definition": "A participant in the community.", "status": "partial",
            "source": "explicit", "excerpt": "community members",
        },
        {
            "name": "Shared resource", "kind": "resource",
            "definition": "A resource accessed by members.", "status": "partial",
            "source": "inferred", "excerpt": "",
        },
    ],
    "properties": [
        {
            "concept": "Shared resource", "name": "availability",
            "data_type": "number", "unit": "units", "definition": "Amount currently available.",
            "status": "proposed", "source": "suggested", "excerpt": "",
        }
    ],
    "relationships": [
        {
            "source_concept": "Community member", "target_concept": "Shared resource",
            "label": "accesses", "description": "Members can access the resource.",
            "directed": True, "status": "partial", "source": "explicit",
            "excerpt": "members access a shared resource",
        }
    ],
    "mechanisms": [
        {
            "name": "Resource allocation", "description": "Allocation mechanism is not fully specified.",
            "inputs": ["Community member", "Shared resource"], "outputs": ["Shared resource"],
            "trigger": "A member requests access.", "effect": "Availability may change.",
            "operational_definition": "", "status": "proposed", "source": "inferred", "excerpt": "",
        }
    ],
    "hypotheses": [
        {"statement": "Clear rules may improve cooperation.", "scope": "Within the community.",
         "source": "suggested", "excerpt": ""}
    ],
    "assumptions": [
        {"statement": "Members can observe the resource state.", "scope": "Initial model.",
         "rationale": "Needed for one possible mechanism.", "source": "inferred", "excerpt": ""}
    ],
    "constraints": [],
    "clarification_questions": [
        {"question": "What is the shared resource?", "reason": "Its type changes the relevant properties.",
         "related_concepts": ["Shared resource"], "blocking": True, "priority": "high"}
    ],
    "uncertainties": ["The allocation rule is not yet defined."],
    "retrieval_queries": ["community shared resource cooperation"],
}


def draft_copy():
    return deepcopy(BASE_DRAFT)
