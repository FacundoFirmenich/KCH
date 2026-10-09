# Jev and open System One sensors

This integration concerns **TypeSafe Jev**, including its typed-decision analogues. It does not concern JEPA. A sensor can supply evidence to RDSS and KCH; a prediction, confidence value, or question named `authority_choice` does not grant execution authority.

## Implemented adapter

`kch_composed.sensors.SystemOneSensor` accepts an explicitly selected callable with the `system_one(state, questions)` interface. `evaluate()` calls that backend and returns an immutable `SensorObservation`; `to_dict()` produces a detached representation suitable for a caller-controlled evidence journal.

The existing LSD experiment runners already use this interface with Laya and OpenDecider. A TypeSafe client can bind its selected model before passing its `system_one` method. MiniSystemOne's existing runner has a separate predictor interface and normalizes its outputs into RDSS receipts. `import_rdss_receipt()` accepts those normalized historical receipts, as well as the Jev, Laya, and OpenDecider receipt families.

The adapter preserves Choice, Score, and Noul values, native distributions, optional confidence, raw response, source reference, and request/response hashes. Choice keeps `ABSTAIN` and `OTHER`. Noul receives no invented confidence statistic. Question hashes preserve criteria order. A truncated state, missing required answer, malformed probability distribution, or closed-set stress receipt cannot become an accepted signal.

Every observation has `mode=SENSOR_ONLY`, `authority=NONE`, and `promotion_allowed=false`. The configured model revision is explicitly labelled caller-supplied, not independently runtime-attested. Historical receipt revisions must agree with the supplied revision. The sensor module does not persist data, load weights, discover credentials, authorize network requests, execute tools, or automatically select another provider. Provider exception messages are excluded from error observations because they may contain private request data or credentials.

**Backend configuration and model execution are separate steps.** The new adapter has passed local protocol tests; this change did not configure a live Jev account, start Laya or OpenDecider inference, or rerun the scientific workflows. A compatible callable must be registered by the trusted host, outside model-generated arguments.

`open-alternative-jev` is also relevant: its `so1` Python package extracts constrained next-token probabilities. Its repository explicitly distinguishes the library from a drop-in Jev HTTP endpoint. A specific output adapter remains necessary before claiming direct compatibility with this integration.

## Own experimental evidence

Historical RDSS evidence is maintained separately with its original access controls. No private workflow aggregates or repository references are published in this source package. The interface supports importing actual receipts without promoting them to execution authority.

## Verification boundary

Thirteen local protocol tests passed. Positive examples use documented numerical responses from TypeSafe's official primitive pages. Rejection tests deliberately corrupt those protocol examples and are labelled as contract tests. They demonstrate parsing, preservation, abstention, immutability, and safe error handling; they do not demonstrate inference quality, calibration, model loading, or end-to-end production integration.

## Primary references

- [TypeSafe primitive contracts](https://docs.typesafe.ai/primitives): [Choice](https://docs.typesafe.ai/primitives/choice), [Score](https://docs.typesafe.ai/primitives/score), [Noul](https://docs.typesafe.ai/primitives/noul).
- [Laya source](https://github.com/NandhaKishorM/laya) and [weights](https://huggingface.co/convaiinnovations/laya).
- [MiniSystemOne source](https://github.com/Colvin0315/MiniSystemOne).
- [OpenDecider nano weights](https://huggingface.co/manjunathshiva/opendecider-nano).
- [Open Alternative to Jev](https://github.com/ikermoel/open-alternative-jev).
