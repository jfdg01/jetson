# Whole-frame resolution sweep — Jetson Q8_0

RefDrone well-posed val (n=439) · Orin Nano 8 GB @ 15 W · Q8_0 · llama.cpp 57fe1f0 · 2026-06-30
(Regenerated from `run.log`; the run's own `per_sample.csv`/`summary.md` write crashed when the
`results/`→`experiments/` dir rename landed mid-run — aggregates below are from `run.log`, intact.)

| max_side | parse% | IoU@0.25 | mean IoU | prefill | decode | wall |
|---|---|---|---|---|---|---|
| 512  | 100.0% | 31.4% | 0.187 | 241 tok / 816 ms  | 12 tok / 543 ms | 1424 ms |
| 1024 | 100.0% | 63.1% | 0.477 | 837 tok / 3712 ms | 12 tok / 547 ms | 4400 ms |
| 1536 | 100.0% | 65.4% | 0.519 | 1383 tok / 7929 ms | 12 tok / 550 ms | 8686 ms |
| 1920 | 100.0% | 65.1% | 0.514 | 1383 tok / 7938 ms | 12 tok / 550 ms | 8689 ms |
