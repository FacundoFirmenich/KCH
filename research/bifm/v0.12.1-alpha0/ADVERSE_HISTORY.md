# BIFM v0.12.1 adverse history — non-finite top-1 repair

The frozen v0.12.0 TALON core correctly restored non-finite mask positions after its main transform, but the top-1 preservation blend reused the restored tensor. A NaN in a masked position could therefore contaminate the row maximum and replace an originally finite winning logit with NaN. The historical diagnostic could still report top-1 preservation because raw `argmax` over NaN obscured the defect.

Adverse witness:

```text
[5, 4, -Inf, NaN, 1, 0, -1, -2, -3, -4]
```

The frozen v0.12.0 output can produce NaN at the original winner during repair while the original NaN/-Inf masks remain present.

v0.12.1 is a future-only software successor. It:

- computes original and final top-1 only over finite candidates;
- blends only finite values during top-1 repair;
- restores the original non-finite mask after repair;
- is bit-identical to v0.12.0 on all 24 finite canonical arm-by-shape cases;
- passes six successor tests, including two non-finite adversarial families.

This correction does not rewrite or promote any historical Spanish sensor or Phi-4 actuator result. The fresh InternLM/C-Eval campaign remains unexecuted and branch authority remains `NONE`.
