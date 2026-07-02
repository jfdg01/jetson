# Run `20260702T231507Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-02T23:15:07.937984+00:00
- **git SHA:** `20c7c3b0555f5bd481542aa0f555b71f984ae9b3`  ⚠️ DIRTY TREE
- **llama.cpp commit:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`
- **lock sha256:** `8766f2dbfc806e5f6938dbd1715e228180ac778a04f4f2bacc03abda422c2b7a`
- **python / platform:** 3.12.10 / Linux-6.17.0-35-generic-x86_64-with-glibc2.39

## Config

```json
{
  "caption": "the white car",
  "loss_s": 3.0,
  "occ": [
    30.0,
    5.0
  ],
  "speed": 1.5,
  "duration_s": 75.0,
  "hz": 20,
  "image_size": 1024,
  "sam2": "facebook/sam2.1-hiera-tiny",
  "validate": "sizeprior-0.5-2.0",
  "deadreckon": true,
  "twin": null,
  "loss_gate": "motion",
  "score_tau": 0.0,
  "dr": "pursuit",
  "acquire_hold": "motion",
  "catchup_replay": true,
  "carry": "host-3090"
}
```

## Results

```json
{
  "trial": {
    "speed_ms": 1.5,
    "image_size": 1024,
    "n_frames": 1462,
    "achieved_hz": 19.5,
    "carry_fps": 20.4,
    "in_fov_frac": 1.0,
    "first_lock_s": 4.66,
    "n_acquire_attempts": 12,
    "n_rejected_acquires": 10,
    "acquire_log": [
      [
        2.35,
        [
          288.0,
          355.2,
          307.2,
          480.0
        ],
        false
      ],
      [
        4.66,
        [
          262.4,
          0.0,
          403.2,
          235.2
        ],
        true
      ],
      [
        35.19,
        [
          38.4,
          43.2,
          64.0,
          67.2
        ],
        false
      ],
      [
        37.49,
        [
          409.6,
          0.0,
          640.0,
          24.0
        ],
        false
      ],
      [
        39.9,
        [
          0.0,
          177.6,
          640.0,
          480.0
        ],
        false
      ],
      [
        42.25,
        [
          352.0,
          244.8,
          377.6,
          364.8
        ],
        false
      ],
      [
        44.65,
        [
          358.4,
          451.2,
          364.8,
          480.0
        ],
        false
      ],
      [
        47.06,
        [
          364.8,
          417.6,
          384.0,
          480.0
        ],
        false
      ],
      [
        49.46,
        [
          384.0,
          393.6,
          403.2,
          480.0
        ],
        false
      ],
      [
        51.86,
        [
          390.4,
          364.8,
          416.0,
          480.0
        ],
        false
      ],
      [
        54.22,
        [
          403.2,
          340.8,
          428.8,
          465.6
        ],
        false
      ],
      [
        56.52,
        [
          396.8,
          0.0,
          531.2,
          225.6
        ],
        true
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      23.59
    ],
    "carry_px_err_mean": 79.0,
    "carry_frames": 837,
    "recovered_after_occlusion": true
  },
  "gate_speed_ms": 1.5,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
