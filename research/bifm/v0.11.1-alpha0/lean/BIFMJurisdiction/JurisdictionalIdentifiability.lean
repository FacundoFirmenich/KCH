namespace BIFMJurisdiction

universe u v w i

variable {M : Type u} {Y : Type v} {Q : Type w} {I : Type i}

/-- A jurisdiction is represented extensionally by a membership predicate. -/
abbrev Jurisdiction (M : Type u) := M → Prop

/-- Identifiability restricted to one jurisdiction. -/
def IdentifiableOn (J : Jurisdiction M) (O : M → Y) (q : M → Q) : Prop :=
  ∀ a b : M, J a → J b → O a = O b → q a = q b

/-- Cross-jurisdiction compatibility: equal observations across two
jurisdictions must receive equal target-property values. -/
def CrossCompatible
    (J K : Jurisdiction M) (O : M → Y) (q : M → Q) : Prop :=
  ∀ a b : M, J a → K b → O a = O b → q a = q b

/-- Union of two jurisdictions. -/
def UnionJ (J K : Jurisdiction M) : Jurisdiction M :=
  fun m => J m ∨ K m

/-- Local identification plus cross-compatibility is sufficient for
identification on a union. -/
theorem identifiableOn_union_of_local_and_cross
    (J K : Jurisdiction M) (O : M → Y) (q : M → Q)
    (hJ : IdentifiableOn J O q)
    (hK : IdentifiableOn K O q)
    (hJK : CrossCompatible J K O q)
    (hKJ : CrossCompatible K J O q) :
    IdentifiableOn (UnionJ J K) O q := by
  intro a b ha hb hObs
  rcases ha with haJ | haK
  · rcases hb with hbJ | hbK
    · exact hJ a b haJ hbJ hObs
    · exact hJK a b haJ hbK hObs
  · rcases hb with hbJ | hbK
    · exact hKJ a b haK hbJ hObs
    · exact hK a b haK hbK hObs

/-- Identification on a union implies identification on each component. -/
theorem identifiableOn_left_of_union
    (J K : Jurisdiction M) (O : M → Y) (q : M → Q)
    (h : IdentifiableOn (UnionJ J K) O q) :
    IdentifiableOn J O q := by
  intro a b ha hb hObs
  exact h a b (Or.inl ha) (Or.inl hb) hObs

/-- Identification on a union implies cross-jurisdiction compatibility. -/
theorem crossCompatible_of_identifiableOn_union
    (J K : Jurisdiction M) (O : M → Y) (q : M → Q)
    (h : IdentifiableOn (UnionJ J K) O q) :
    CrossCompatible J K O q := by
  intro a b ha hb hObs
  exact h a b (Or.inl ha) (Or.inr hb) hObs

/-- Exact two-jurisdiction gluing theorem. -/
theorem identifiableOn_union_iff
    (J K : Jurisdiction M) (O : M → Y) (q : M → Q) :
    IdentifiableOn (UnionJ J K) O q ↔
      IdentifiableOn J O q ∧
      IdentifiableOn K O q ∧
      CrossCompatible J K O q ∧
      CrossCompatible K J O q := by
  constructor
  · intro h
    refine ⟨identifiableOn_left_of_union J K O q h, ?_⟩
    refine ⟨identifiableOn_left_of_union K J O q ?_, ?_⟩
    · intro a b ha hb hObs
      exact h a b (Or.inr ha) (Or.inr hb) hObs
    · exact ⟨crossCompatible_of_identifiableOn_union J K O q h,
             crossCompatible_of_identifiableOn_union K J O q ?_⟩
      intro a b ha hb hObs
      exact h a b (Or.inr ha) (Or.inl hb) hObs
  · rintro ⟨hJ, hK, hJK, hKJ⟩
    exact identifiableOn_union_of_local_and_cross J K O q hJ hK hJK hKJ

/-- An indexed family covers a target jurisdiction. -/
def Covers (U : Jurisdiction M) (Js : I → Jurisdiction M) : Prop :=
  ∀ m : M, U m ↔ ∃ i : I, Js i m

/-- Pairwise compatibility of an indexed jurisdiction family. -/
def PairwiseCompatible
    (Js : I → Jurisdiction M) (O : M → Y) (q : M → Q) : Prop :=
  ∀ i j : I, CrossCompatible (Js i) (Js j) O q

/-- Local identification plus pairwise compatibility glues over an arbitrary
indexed cover. -/
theorem identifiableOn_of_cover
    (U : Jurisdiction M) (Js : I → Jurisdiction M)
    (O : M → Y) (q : M → Q)
    (hCover : Covers U Js)
    (hLocal : ∀ i : I, IdentifiableOn (Js i) O q)
    (hCompat : PairwiseCompatible Js O q) :
    IdentifiableOn U O q := by
  intro a b ha hb hObs
  rcases (hCover a).mp ha with ⟨i, hai⟩
  rcases (hCover b).mp hb with ⟨j, hbj⟩
  exact hCompat i j a b hai hbj hObs

/-- Local identifiability alone is not enough: a conflicting cross-jurisdiction
pair is a constructive obstruction to global gluing. -/
theorem cross_witness_refutes_global
    (U J K : Jurisdiction M) (O : M → Y) (q : M → Q)
    (hJU : ∀ m, J m → U m)
    (hKU : ∀ m, K m → U m)
    {a b : M}
    (ha : J a) (hb : K b)
    (hObs : O a = O b)
    (hQ : q a ≠ q b) :
    ¬ IdentifiableOn U O q := by
  intro hIdent
  exact hQ (hIdent a b (hJU a ha) (hKU b hb) hObs)

end BIFMJurisdiction
