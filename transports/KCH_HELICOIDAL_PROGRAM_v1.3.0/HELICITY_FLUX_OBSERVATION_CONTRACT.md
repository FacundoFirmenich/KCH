# Helicity-flux observation contract — v1.3

## 1. Claim jurisdiction

This gate concerns the **photospheric injection rate of relative magnetic helicity**. It does not estimate the relative magnetic helicity already stored in a coronal volume.

The hierarchy is therefore:

```text
vector field B(x,y,t)
  -> induction-compatible velocity V(x,y,t)
  -> perpendicular transport V_perp
  -> reference potential-field vector potential A_p
  -> photospheric relative-helicity injection dH_R/dt
```

No implication to coronal (H_R) is authorized without a separately frozen volume, boundary and gauge-equivalent 3-D reconstruction.

## 2. Surface-flux definition

For a photospheric surface (S),

[
rac{dH_R}{dt}Big|_S
=
2int_S (mathbf A_pcdotmathbf B_h)V_{perp n},dS
-
2int_S (mathbf A_pcdotmathbf V_{perp h})B_n,dS.
]

The reference potential field shares the observed normal field on the boundary. In the planar Coulomb construction used in this qualification gate,

[

abla_hcdotmathbf A_p=0,qquad
mathbf A_pcdothat{mathbf n}=0,qquad
(
abla	imesmathbf A_p)cdothat{mathbf n}=B_n.
]

The open-plane Green representation is

[
mathbf A_p(mathbf x)
=
rac{1}{2pi}hat{mathbf n}	imes
int_S B_n(mathbf x')
rac{mathbf x-mathbf x'}{|mathbf x-mathbf x'|^2},dS'.
]

This implementation is treated as an **operator under test**, not as an assumed truth: its numerical curl must reconstruct the observed normal field within the prelocked correlation and normalized-RMSE gates.

## 3. Velocity inference

The gate uses DAVE4VM, which constrains a local affine velocity field using the normal component of the ideal induction equation and vector magnetogram information.

The exact implementation is pinned to:

```text
Hypnus1803/pyflowmaps
commit c231189ae9134b7578d431a062ccc132565fba1d
MIT license
```

Only the core `pydave4vm` operator and its finite-difference helper are used. Higher-level wrappers are outside the frozen runtime.

The inferred velocity is subsequently projected perpendicular to the magnetic field,

[
mathbf V_perp
=
mathbf V
-
rac{mathbf Vcdotmathbf B}{|mathbf B|^2}mathbf B.
]

This removes the field-aligned component, which does not enter the ideal electric field.

## 4. Identifiability gates

A finite number for (dH_R/dt) is not sufficient evidence that the operator is identifiable. Qualification requires all of the following classes of tests:

1. **synthetic recovery** — a known transported vector field must yield the imposed velocity within the frozen tolerance;
2. **induction residual** — the inferred velocity must reduce the held normal-induction residual relative to zero velocity;
3. **potential-vector reconstruction** — (
abla	imes A_p) must recover (B_n);
4. **time reversal** — reversing the magnetogram pair must reverse (dH_R/dt);
5. **orientation/parity control** — the pseudoscalar injection must transform with the correct sign under the frozen orientation reversal;
6. **window stability** — 13- and 19-pixel DAVE4VM apertures must agree in sign for at least three of four real regions and satisfy the median effect-stability bound;
7. **cadence stability** — the centered 24-minute estimate must agree with the average of adjacent 12-minute estimates under the same rule;
8. **boundary identifiability** — excessive signed flux imbalance triggers abstention rather than silent gauge/boundary extrapolation.

## 5. Epistemic outcomes

`HELICITY_FLUX_OPERATOR_QUALIFIED` means only that this measurement operator is sufficiently stable to be used in a later prospective scientific gate.

It does **not** mean:

- helicity injection has a preferred sign;
- helicity injection predicts flares or CMEs;
- current helicity and helicity flux are interchangeable;
- photospheric flux equals coronal stored helicity;
- helicity is a universal organizing principle.

Failure of this gate blocks the later helicity-flux science gate. It does not negate magnetic helicity as a physical invariant.

## 6. References fixed for the operator family

- Berger & Field (1984), *The topological properties of magnetic helicity*, Journal of Fluid Mechanics.
- Schuck (2008), *Tracking Vector Magnetograms with the Magnetic Induction Equation*, Astrophysical Journal 683, 1134–1152.
- Pariat, Démoulin & Berger (2005), helicity-flux density formulation.
- Liu & Schuck (2012/2013), vector-magnetogram helicity/energy-flux implementations and fast evaluation.
- ARTop (Alielden et al. 2023), open-source active-region topology and DAVE4VM workflow, used as an external implementation reference but not as the frozen primary numerical operator in this gate.
