# Run `20260625T234617Z` — eval

- **Created (UTC):** 2026-06-25T23:46:17.845213+00:00
- **git SHA:** `599bde2f6cb23d7e595d5e48525110beae6a0f73`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `c85c39dfe299fff25dd94b8a84ffa4ae2a65a3a79146e6efd38c8b51d02f9ad7`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "phase": "II/III",
  "experiment": "roi-crop-anchor",
  "backend": "hf",
  "model": "./runs/v2/phase3-refdrone-1024",
  "dataset": "refdrone",
  "split": "val",
  "n": 439,
  "roi_margin": 5.0,
  "roi_out_res": "native",
  "perturb_shift": 0.0,
  "perturb_scale": 1.0,
  "device": "cuda",
  "dtype": "bfloat16",
  "note": "roi survivors + baseline, full val"
}
```

## Results

```json
{
  "backend": "hf",
  "n": 439,
  "parse_rate": 0.9954441913439636,
  "iou_gate_pass_rate": 0.6697038724373576,
  "mean_iou": 0.5546006050491471,
  "center_std": 229.80889631460457
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
