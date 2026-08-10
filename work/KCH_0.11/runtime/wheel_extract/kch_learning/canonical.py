from __future__ import annotations

from enum import StrEnum


class LearningChannel(StrEnum):
    OBL = "OBL"
    PHL = "PHL"


class Initiator(StrEnum):
    USER = "USER"
    MODEL = "MODEL"


class FeedbackVerdict(StrEnum):
    ACCEPT = "ACCEPT"
    CORRECT = "CORRECT"
    ABSTAIN = "ABSTAIN"


OBL_EXPANSION = "ONBOARDING_LEARNING"
PHL_EXPANSION = "POST_HOC_LEARNING"
PHL_SCORE_SCHEMA = {
    "format": "ZERO_PADDED_INTEGER_000_TO_100",
    "known_anchor": {"100": "MAXIMUM_POSITIVE_10_OF_10"},
    "unasserted_properties": [
        "NO_NEUTRAL_POINT_ASSUMED",
        "NO_EQUAL_INTERVAL_DISTANCE_ASSUMED",
        "NO_AUTOMATIC_REWARD_MAPPING",
    ],
}


class LearningError(ValueError):
    pass
