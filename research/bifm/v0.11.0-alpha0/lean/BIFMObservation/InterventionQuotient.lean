namespace BIFMObservation

universe u v w x

variable {E : Type u} {M : Type v} {Y : Type w} {Q : Type x}

/-- Two intervention commands are realization-equivalent when an architecture
maps them to exactly the same realized state. -/
def RealizationEquivalent (R : E → M) (e₁ e₂ : E) : Prop :=
  R e₁ = R e₂

/-- Realization equivalence is reflexive. -/
theorem realizationEquivalent_refl (R : E → M) (e : E) :
    RealizationEquivalent R e e := by
  rfl

/-- Realization equivalence is symmetric. -/
theorem realizationEquivalent_symm (R : E → M) {e₁ e₂ : E}
    (h : RealizationEquivalent R e₁ e₂) :
    RealizationEquivalent R e₂ e₁ := by
  exact h.symm

/-- Realization equivalence is transitive. -/
theorem realizationEquivalent_trans (R : E → M) {e₁ e₂ e₃ : E}
    (h₁₂ : RealizationEquivalent R e₁ e₂)
    (h₂₃ : RealizationEquivalent R e₂ e₃) :
    RealizationEquivalent R e₁ e₃ := by
  exact h₁₂.trans h₂₃

/-- Every observation necessarily collapses commands already collapsed by the
architecture-relative realization map. -/
theorem realization_equivalence_implies_observational_equivalence
    (R : E → M) (O : M → Y) {e₁ e₂ : E}
    (h : RealizationEquivalent R e₁ e₂) :
    O (R e₁) = O (R e₂) := by
  exact congrArg O h

/-- Observation equivalence may hold despite distinct realized states. -/
def ObservationEquivalentAfterRealization
    (R : E → M) (O : M → Y) (e₁ e₂ : E) : Prop :=
  O (R e₁) = O (R e₂)

/-- A pure observation-induced collision has equal observations but unequal
realized states. -/
def ObservationCollisionAfterRealization
    (R : E → M) (O : M → Y) (e₁ e₂ : E) : Prop :=
  O (R e₁) = O (R e₂) ∧ R e₁ ≠ R e₂

/-- A realization collision is always a collision of the composite map. -/
theorem realization_collision_in_composite
    (R : E → M) (O : M → Y) {e₁ e₂ : E}
    (h : RealizationEquivalent R e₁ e₂) :
    ObservationEquivalentAfterRealization R O e₁ e₂ := by
  exact realization_equivalence_implies_observational_equivalence R O h

/-- If a property of realized states is identifiable from the observation,
then equal observations imply equal property values even when controls differ. -/
def IdentifiableRealizedProperty
    (O : M → Y) (q : M → Q) : Prop :=
  ∀ m₁ m₂ : M, O m₁ = O m₂ → q m₁ = q m₂

/-- Realized-property identifiability lifts through the realization map. -/
theorem identifiable_realized_property_lifts_to_controls
    (R : E → M) (O : M → Y) (q : M → Q)
    (hIdent : IdentifiableRealizedProperty O q) :
    ∀ e₁ e₂ : E, O (R e₁) = O (R e₂) → q (R e₁) = q (R e₂) := by
  intro e₁ e₂ hObs
  exact hIdent (R e₁) (R e₂) hObs

/-- Distinct control commands cannot be identified from the realized state when
R maps them to the same state. -/
def ControlIdentifiableFromRealization (R : E → M) : Prop :=
  ∀ e₁ e₂ : E, R e₁ = R e₂ → e₁ = e₂

/-- A nontrivial realization-equivalent command pair refutes control
identifiability from realized state. -/
theorem realization_witness_refutes_control_identifiability
    (R : E → M) {e₁ e₂ : E}
    (hReal : RealizationEquivalent R e₁ e₂)
    (hControl : e₁ ≠ e₂) :
    ¬ ControlIdentifiableFromRealization R := by
  intro hIdent
  exact hControl (hIdent e₁ e₂ hReal)

end BIFMObservation
