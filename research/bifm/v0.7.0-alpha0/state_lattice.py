from dataclasses import dataclass, asdict

SCOPE=("IN_SCOPE","OUT_OF_SCOPE")
STRUCTURAL=("IDENTIFIABLE","NOT_IDENTIFIABLE","NOT_APPLICABLE")
STABILITY=("STABLE","ILL_CONDITIONED","UNKNOWN","NOT_APPLICABLE")
RECOVERY=("NONE_NEEDED","RESTRICTION_AVAILABLE","PROBE_AVAILABLE","NO_CERTIFIED_RECOVERY","NOT_APPLICABLE")
SEMANTIC=("FORMAL_CERTIFIED","CNL_ROUNDTRIP_CERTIFIED","OPEN_WORLD_UNCERTIFIED")

@dataclass(frozen=True)
class CertificateState:
    scope: str
    structural: str
    stability: str
    recovery: str
    semantic: str="FORMAL_CERTIFIED"

    def validate(self):
        assert self.scope in SCOPE
        assert self.structural in STRUCTURAL
        assert self.stability in STABILITY
        assert self.recovery in RECOVERY
        assert self.semantic in SEMANTIC
        if self.scope=="OUT_OF_SCOPE":
            assert self.structural=="NOT_APPLICABLE"
            assert self.stability=="NOT_APPLICABLE"
            assert self.recovery=="NOT_APPLICABLE"
        if self.structural=="IDENTIFIABLE":
            assert self.recovery=="NONE_NEEDED"
        return self

V06_TO_AXES={
    "IDENTIFIABLE": CertificateState("IN_SCOPE","IDENTIFIABLE","UNKNOWN","NONE_NEEDED"),
    "PRACTICALLY_UNSTABLE": CertificateState("IN_SCOPE","IDENTIFIABLE","ILL_CONDITIONED","NONE_NEEDED"),
    "NOT_IDENTIFIABLE": CertificateState("IN_SCOPE","NOT_IDENTIFIABLE","UNKNOWN","NO_CERTIFIED_RECOVERY"),
    "CONDITIONALLY_IDENTIFIABLE": CertificateState("IN_SCOPE","NOT_IDENTIFIABLE","UNKNOWN","RESTRICTION_AVAILABLE"),
    "RECOVERABLE_BY_PROBE": CertificateState("IN_SCOPE","NOT_IDENTIFIABLE","UNKNOWN","PROBE_AVAILABLE"),
    "OUT_OF_SCOPE": CertificateState("OUT_OF_SCOPE","NOT_APPLICABLE","NOT_APPLICABLE","NOT_APPLICABLE"),
}
AXES_TO_V06={v:k for k,v in V06_TO_AXES.items()}

def from_v06(status):
    return V06_TO_AXES[status].validate()

def to_dict(state):
    return asdict(state)
