from __future__ import annotations
import importlib.util, json, pathlib, torch

HERE = pathlib.Path(__file__).resolve().parent
OLD = HERE.parent / "v0.12.0-alpha0" / "talamo_exact.py"
NEW = HERE / "talamo_exact.py"
CONFIGS = HERE.parent / "v0.12.0-alpha0" / "canonical_configs.json"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


old = load(OLD, "talamo_v0120")
new = load(NEW, "talamo_v0121")
configs = json.loads(CONFIGS.read_text())


def make(module, name, cfg):
    cfg = dict(cfg)
    family = cfg.pop("family")
    cfg["debug"] = False
    config_cls = module.TALMOperatorConfig if family == "TALM" else module.TALONOperatorConfig
    processor_cls = module.TALMLogitProcessor if family == "TALM" else module.TALONLogitProcessor
    return processor_cls(config_cls(**cfg))


def safe_top1(x):
    finite = torch.isfinite(x)
    view = torch.where(finite, x, torch.tensor(-torch.inf, dtype=x.dtype))
    return torch.argmax(view, dim=-1)


def test_finite_inputs_are_bit_identical():
    generator = torch.Generator().manual_seed(20261022)
    for name, cfg in configs.items():
        for shape in ((1, 257), (4, 257), (2, 1024)):
            x = torch.randn(*shape, generator=generator)
            a = make(old, name, cfg)(torch.zeros((shape[0], 1), dtype=torch.long), x.clone())
            b = make(new, name, cfg)(torch.zeros((shape[0], 1), dtype=torch.long), x.clone())
            assert torch.equal(a, b), (name, shape)


def test_nonfinite_mask_does_not_poison_finite_winner():
    x = torch.tensor([[5., 4., float("-inf"), float("nan"), 1., 0., -1., -2., -3., -4.]])
    cfg = dict(family="TALON", strength=.75, temperature=1.0,
               mass_threshold=.92, selection_mode="mass", side_policy="right",
               preserve_top1=True)
    old_out = make(old, "adverse", cfg)(torch.zeros((1, 1), dtype=torch.long), x.clone())
    new_out = make(new, "adverse", cfg)(torch.zeros((1, 1), dtype=torch.long), x.clone())
    assert torch.isnan(old_out[0, 0])
    assert torch.isfinite(new_out[0, 0])
    assert safe_top1(new_out).item() == 0
    assert torch.isneginf(new_out[0, 2]) and torch.isnan(new_out[0, 3])


def test_multiple_rows_and_all_masked_row_fail_closed():
    x = torch.tensor([
      [5., 4., float("-inf"), float("nan"), 1., 0., -1., -2., -3., -4.],
      [1., float("-inf"), .9, .8, float("nan"), .1, 0., -.1, -.2, -.3],
      [float("-inf"), float("nan"), float("-inf"), float("nan"),
       float("-inf"), float("nan"), float("-inf"), float("nan"),
       float("-inf"), float("nan")],
    ])
    cfg = dict(family="TALON", strength=.75, temperature=1.0,
               mass_threshold=.92, selection_mode="mass", side_policy="right",
               preserve_top1=True)
    y = make(new, "adverse_rows", cfg)(torch.zeros((3, 1), dtype=torch.long), x.clone())
    assert safe_top1(y[:2]).tolist() == [0, 0]
    assert torch.equal(torch.isfinite(y), torch.isfinite(x))
    assert torch.equal(torch.isnan(y), torch.isnan(x))
    assert torch.equal(torch.isneginf(y), torch.isneginf(x))
