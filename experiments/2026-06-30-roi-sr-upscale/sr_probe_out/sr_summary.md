# ROI super-resolution probe

crop 400x400 oracle · feed 1024 · n=429 samples (GT fits crop, long edge <= 300px)

| method | parse% | IoU@0.25 | mean IoU | med SR ms | med VLM ms |
|---|---|---|---|---|---|
| native | 100.0% | 78.8% | 0.651 | 0 | 306 |
| bicubic | 100.0% | 80.9% | 0.695 | 0 | 635 |
| lanczos | 100.0% | 80.2% | 0.690 | 0 | 634 |
| swin2sr | 100.0% | 78.6% | 0.682 | 1331 | 635 |
