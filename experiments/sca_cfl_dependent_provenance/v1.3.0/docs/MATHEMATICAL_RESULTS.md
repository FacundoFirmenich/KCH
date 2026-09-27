# Robust evidence under uncertain genealogy

Let G* be the unknown true genealogy and Γ_t a family of genealogies compatible with authorized provenance constraints, with G* in Γ_t. For each G, let E_t^G be the root-level e-process valid if G is true. Define

E_t^rob = inf_{G in Γ_t} E_t^G.

Pointwise E_t^rob <= E_t^{G*}; hence for any stopping time τ,

E[E_τ^rob] <= E[E_τ^{G*}] <= 1.

Thus genealogy uncertainty can only discount evidentiary capital, provided the true genealogy has not been excluded by a false hard constraint.

The implementation exactly enumerates compatible partitions for up to ten must-same components and fails closed above that limit.
