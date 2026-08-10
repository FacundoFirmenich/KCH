"""MIS v0.3.1: exact Bayesian decision calculus over native qualitative atoms."""

from .atoms import AtomRegistry, SemanticAtom
from .decision import BayesDecision, LossTable, bayes_decide
from .exact import ExactDistribution, ZeroEvidenceError, categorical_brier, dirichlet_predictive
from .freeze import FrozenRound, FutureOnlyLedger, OutcomeReceipt
from .khc import (
    KHCCorpus,
    KHCDecisionRecord,
    MISKHCDecisionUnit,
    constitute_units,
    integration_audit,
    khc_action_registry,
    load_khc_corpus,
)

__all__ = [
    "AtomRegistry",
    "BayesDecision",
    "ExactDistribution",
    "FrozenRound",
    "FutureOnlyLedger",
    "KHCCorpus",
    "KHCDecisionRecord",
    "LossTable",
    "MISKHCDecisionUnit",
    "OutcomeReceipt",
    "SemanticAtom",
    "ZeroEvidenceError",
    "bayes_decide",
    "categorical_brier",
    "constitute_units",
    "dirichlet_predictive",
    "integration_audit",
    "khc_action_registry",
    "load_khc_corpus",
]

__version__ = "0.3.1"
