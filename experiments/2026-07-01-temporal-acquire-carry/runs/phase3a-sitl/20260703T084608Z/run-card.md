# Run `20260703T084608Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T08:46:08.021001+00:00
- **git SHA:** `2344f6ab6c1d39dd49dc8f2ddb93a7034d56168b`  ⚠️ DIRTY TREE
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
  "speed": 1.0,
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
  "reground_gate": "motion",
  "catchup_replay": true,
  "carry": "host-3090"
}
```

## Results

```json
{
  "trial": {
    "speed_ms": 1.0,
    "image_size": 1024,
    "n_frames": 1458,
    "achieved_hz": 19.4,
    "carry_fps": 20.5,
    "in_fov_frac": 1.0,
    "first_lock_s": 4.66,
    "n_acquire_attempts": 5,
    "n_rejected_acquires": 3,
    "n_reground_gate_rejects": 0,
    "acquire_log": [
      [
        2.35,
        [
          288.0,
          355.2,
          307.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        4.66,
        [
          256.0,
          33.6,
          396.8,
          288.0
        ],
        true,
        ""
      ],
      [
        35.24,
        [
          307.2,
          388.8,
          326.4,
          427.2
        ],
        false,
        "size"
      ],
      [
        37.5,
        [
          307.2,
          0.0,
          448.0,
          24.0
        ],
        false,
        "size"
      ],
      [
        39.8,
        [
          326.4,
          0.0,
          448.0,
          163.2
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      6.92
    ],
    "carry_px_err_mean": 55.2,
    "carry_frames": 1166,
    "recovered_after_occlusion": true
  },
  "gate_speed_ms": 1.0,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
