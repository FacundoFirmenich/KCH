--------------------------- MODULE PCGT ---------------------------
EXTENDS Naturals, Sequences, FiniteSets, TLC

CONSTANTS Stages, Planes, Decisions

VARIABLES stage, plane, decision, jurisdiction, cas, authority,
          lease, qas, effect, receipt, outcome, futureUpdate,
          generation, eligibleGeneration

vars == <<stage, plane, decision, jurisdiction, cas, authority,
          lease, qas, effect, receipt, outcome, futureUpdate,
          generation, eligibleGeneration>>

Init ==
  /\ stage = "CREATED"
  /\ plane \in {"PRESENT", "SHADOW"}
  /\ decision = "NONE"
  /\ jurisdiction = FALSE
  /\ cas = FALSE
  /\ authority = FALSE
  /\ lease = FALSE
  /\ qas = FALSE
  /\ effect = FALSE
  /\ receipt = FALSE
  /\ outcome = FALSE
  /\ futureUpdate = FALSE
  /\ generation = 1
  /\ eligibleGeneration = 0

Observe == /\ stage = "CREATED" /\ stage' = "OBSERVED" /\ UNCHANGED <<plane, decision, jurisdiction, cas, authority, lease, qas, effect, receipt, outcome, futureUpdate, generation, eligibleGeneration>>
Candidates == /\ stage = "OBSERVED" /\ stage' = "CANDIDATES" /\ UNCHANGED <<plane, decision, jurisdiction, cas, authority, lease, qas, effect, receipt, outcome, futureUpdate, generation, eligibleGeneration>>
Probe == /\ stage = "CANDIDATES" /\ stage' = "PROBED" /\ UNCHANGED <<plane, decision, jurisdiction, cas, authority, lease, qas, effect, receipt, outcome, futureUpdate, generation, eligibleGeneration>>
Jurisdiction == /\ stage = "PROBED" /\ stage' = "JURISDICTION" /\ jurisdiction' = TRUE /\ UNCHANGED <<plane, decision, cas, authority, lease, qas, effect, receipt, outcome, futureUpdate, generation, eligibleGeneration>>
CAS == /\ stage = "JURISDICTION" /\ jurisdiction /\ stage' = "SUFFICIENCY" /\ cas' = TRUE /\ UNCHANGED <<plane, decision, jurisdiction, authority, lease, qas, effect, receipt, outcome, futureUpdate, generation, eligibleGeneration>>
Authorize == /\ stage = "SUFFICIENCY" /\ cas /\ plane = "PRESENT" /\ stage' = "AUTHORIZED" /\ decision' = "APPLY" /\ authority' = TRUE /\ UNCHANGED <<plane, jurisdiction, cas, lease, qas, effect, receipt, outcome, futureUpdate, generation, eligibleGeneration>>
ShadowDecision == /\ stage = "SUFFICIENCY" /\ plane = "SHADOW" /\ stage' = "SHADOWED" /\ decision' = "SHADOW" /\ UNCHANGED <<plane, jurisdiction, cas, authority, lease, qas, effect, receipt, outcome, futureUpdate, generation, eligibleGeneration>>
Lease == /\ stage = "AUTHORIZED" /\ authority /\ decision = "APPLY" /\ stage' = "LEASED" /\ lease' = TRUE /\ UNCHANGED <<plane, decision, jurisdiction, cas, authority, qas, effect, receipt, outcome, futureUpdate, generation, eligibleGeneration>>
Localize == /\ stage = "LEASED" /\ lease /\ qas = FALSE /\ qas' = TRUE /\ UNCHANGED <<stage, plane, decision, jurisdiction, cas, authority, lease, effect, receipt, outcome, futureUpdate, generation, eligibleGeneration>>
Execute == /\ stage = "LEASED" /\ plane = "PRESENT" /\ authority /\ lease /\ qas /\ stage' = "EXECUTED" /\ effect' = TRUE /\ UNCHANGED <<plane, decision, jurisdiction, cas, authority, lease, qas, receipt, outcome, futureUpdate, generation, eligibleGeneration>>
Receipt == /\ stage = "EXECUTED" /\ effect /\ stage' = "RECEIPTED" /\ receipt' = TRUE /\ UNCHANGED <<plane, decision, jurisdiction, cas, authority, lease, qas, effect, outcome, futureUpdate, generation, eligibleGeneration>>
Outcome == /\ stage = "RECEIPTED" /\ receipt /\ stage' = "OUTCOME" /\ outcome' = TRUE /\ UNCHANGED <<plane, decision, jurisdiction, cas, authority, lease, qas, effect, receipt, futureUpdate, generation, eligibleGeneration>>
Learn == /\ stage = "OUTCOME" /\ outcome /\ stage' = "LEARNING" /\ plane' = "LEARNING" /\ futureUpdate' = TRUE /\ eligibleGeneration' = generation + 1 /\ UNCHANGED <<decision, jurisdiction, cas, authority, lease, qas, effect, receipt, outcome, generation>>

Next == Observe \/ Candidates \/ Probe \/ Jurisdiction \/ CAS \/ Authorize \/ ShadowDecision \/ Lease \/ Localize \/ Execute \/ Receipt \/ Outcome \/ Learn

Spec == Init /\ [][Next]_vars

NoEffectWithoutAuthority == effect => authority
NoEffectWithoutLease == effect => lease
NoEffectWithoutQAS == effect => qas
NoShadowEffect == (plane = "SHADOW") => ~effect
ReceiptRequiresEffect == receipt => effect
OutcomeRequiresReceipt == outcome => receipt
FutureRequiresOutcome == futureUpdate => outcome
FutureOnly == futureUpdate => eligibleGeneration > generation

=============================================================================
