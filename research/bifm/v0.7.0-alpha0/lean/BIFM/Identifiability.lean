namespace BIFM

universe u v w x

variable {M : Type u} {Y : Type v} {Q : Type w} {X : Type x}

def Identifiable (O : M → Y) (q : M → Q) : Prop :=
  ∀ a b, O a = O b → q a = q b

def Collision (O : M → Y) (q : M → Q) : Prop :=
  ∃ a b, O a = O b ∧ q a ≠ q b

theorem identifiable_iff_no_collision (O : M → Y) (q : M → Q) :
    Identifiable O q ↔ ¬ Collision O q := by
  constructor
  · intro h ⟨a, b, hO, hq⟩
    exact hq (h a b hO)
  · intro h a b hO
    by_contra hq
    exact h ⟨a, b, hO, hq⟩

def ObsImage (O : M → Y) := { y : Y // ∃ m : M, O m = y }

theorem identifiable_iff_factors_through_image (O : M → Y) (q : M → Q) :
    Identifiable O q ↔
      ∃ g : ObsImage O → Q, ∀ m : M, g ⟨O m, ⟨m, rfl⟩⟩ = q m := by
  constructor
  · intro h
    classical
    let g : ObsImage O → Q := fun y => q (Classical.choose y.property)
    refine ⟨g, ?_⟩
    intro m
    dsimp [g]
    apply h
    exact Classical.choose_spec (show ∃ m' : M, O m' = O m from ⟨m, rfl⟩)
  · rintro ⟨g, hg⟩ a b hO
    calc
      q a = g ⟨O a, ⟨a, rfl⟩⟩ := (hg a).symm
      _ = g ⟨O b, ⟨b, rfl⟩⟩ := by
        apply congrArg g
        apply Subtype.ext
        exact hO
      _ = q b := hg b

theorem identifiable_monotone_under_probe
    (O : M → Y) (P : M → Q) (target : M → X) :
    Identifiable O target → Identifiable (fun m => (O m, P m)) target := by
  intro h a b hPair
  exact h a b (congrArg Prod.fst hPair)

theorem collision_blocks_factorization (O : M → Y) (q : M → Q) :
    Collision O q → ¬ (∃ g : ObsImage O → Q, ∀ m : M, g ⟨O m, ⟨m, rfl⟩⟩ = q m) := by
  intro hCollision hFactor
  have hIdent : Identifiable O q := (identifiable_iff_factors_through_image O q).2 hFactor
  exact ((identifiable_iff_no_collision O q).1 hIdent) hCollision

end BIFM
