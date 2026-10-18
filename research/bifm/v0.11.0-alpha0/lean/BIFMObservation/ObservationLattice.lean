namespace BIFMObservation

universe u v w x

variable {M : Type u} {Y : Type v} {Z : Type w} {Q : Type x}

/-- A candidate is invisible relative to a baseline under an observation map. -/
def Invisible (O : M → Y) (baseline candidate : M) : Prop :=
  O candidate = O baseline

/-- `fine` refines `coarse` when `coarse` is a deterministic post-processing of `fine`. -/
def Refines (coarse : M → Y) (fine : M → Z) : Prop :=
  ∃ r : Z → Y, ∀ m : M, coarse m = r (fine m)

/-- A target property is identifiable when observation equality entails property equality. -/
def Identifiable (O : M → Y) (q : M → Q) : Prop :=
  ∀ a b : M, O a = O b → q a = q b

/-- Equality under a finer observation implies equality under every coarser observation. -/
theorem invisible_monotone_of_refines
    (coarse : M → Y) (fine : M → Z)
    (baseline candidate : M)
    (hRef : Refines coarse fine)
    (hInv : Invisible fine baseline candidate) :
    Invisible coarse baseline candidate := by
  rcases hRef with ⟨r, hr⟩
  unfold Invisible at hInv ⊢
  calc
    coarse candidate = r (fine candidate) := hr candidate
    _ = r (fine baseline) := congrArg r hInv
    _ = coarse baseline := (hr baseline).symm

/-- Identifiability under a coarse observation is preserved by a finer observation. -/
theorem identifiable_monotone_of_refines
    (coarse : M → Y) (fine : M → Z) (q : M → Q)
    (hRef : Refines coarse fine)
    (hIdent : Identifiable coarse q) :
    Identifiable fine q := by
  intro a b hFine
  rcases hRef with ⟨r, hr⟩
  apply hIdent a b
  calc
    coarse a = r (fine a) := hr a
    _ = r (fine b) := congrArg r hFine
    _ = coarse b := (hr b).symm

/-- Adding a probe produces a refinement of the original observation. -/
theorem pair_refines_left (O : M → Y) (P : M → Z) :
    Refines O (fun m => (O m, P m)) := by
  refine ⟨Prod.fst, ?_⟩
  intro m
  rfl

/-- Adding a probe cannot make an already identifiable target non-identifiable. -/
theorem identifiable_after_adding_probe
    (O : M → Y) (P : M → Z) (q : M → Q)
    (hIdent : Identifiable O q) :
    Identifiable (fun m => (O m, P m)) q := by
  exact identifiable_monotone_of_refines O (fun m => (O m, P m)) q
    (pair_refines_left O P) hIdent

/-- If the fine observation distinguishes a candidate, no conclusion follows for the coarse one. -/
example (coarse : M → Y) (fine : M → Z)
    (baseline candidate : M)
    (hRef : Refines coarse fine)
    (hNotFine : ¬ Invisible fine baseline candidate) : True := by
  trivial

end BIFMObservation
