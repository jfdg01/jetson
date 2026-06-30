# ROI super-resolution probe

crop 400x400 oracle · feed 1024 · n=5 samples (GT fits crop, long edge <= 300px)

| method | parse% | IoU@0.25 | mean IoU | med SR ms | med VLM ms |
|---|---|---|---|---|---|
| native | 100.0% | 60.0% | 0.361 | 0 | 310 |
| bicubic | 100.0% | 60.0% | 0.457 | 0 | 632 |
| lanczos | 100.0% | 60.0% | 0.500 | 0 | 639 |
| swin2sr | 100.0% | 60.0% | 0.457 | 1352 | 634 |
