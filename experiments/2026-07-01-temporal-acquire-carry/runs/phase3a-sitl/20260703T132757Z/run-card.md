# Run `20260703T132757Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T13:27:57.040656+00:00
- **git SHA:** `3b22c68682192d4e831d1cff7515291bb0cd52ab`  ⚠️ DIRTY TREE
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
  "speed": 2.5,
  "duration_s": 75.0,
  "hz": 20,
  "image_size": 1024,
  "sam2": "facebook/sam2.1-hiera-tiny",
  "validate": "sizeprior-0.5-2.0",
  "deadreckon": true,
  "twin": null,
  "retarget_t": null,
  "loss_gate": "motion",
  "score_tau": 0.0,
  "dr": "pursuit",
  "acquire_hold": "chase",
  "reground_gate": "none",
  "vmax": 4.0,
  "catchup_replay": true,
  "carry": "host-3090"
}
```

## Results

```json
{
  "trial": {
    "speed_ms": 2.5,
    "image_size": 1024,
    "n_frames": 1476,
    "duration_s": 75.0,
    "achieved_hz": 19.7,
    "carry_fps": 20.9,
    "in_fov_frac": 1.0,
    "first_lock_s": 2.3,
    "n_acquire_attempts": 8,
    "n_rejected_acquires": 6,
    "n_reground_gate_rejects": 0,
    "acquire_log": [
      [
        2.3,
        [
          243.2,
          76.8,
          396.8,
          340.8
        ],
        true,
        ""
      ],
      [
        35.15,
        [
          44.8,
          43.2,
          57.6,
          48.0
        ],
        false,
        "size"
      ],
      [
        37.4,
        [
          288.0,
          0.0,
          428.8,
          28.8
        ],
        false,
        "size"
      ],
      [
        39.7,
        [
          211.2,
          0.0,
          524.8,
          374.4
        ],
        false,
        "size"
      ],
      [
        42.11,
        [
          345.6,
          441.6,
          358.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        44.46,
        [
          217.6,
          0.0,
          563.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        46.86,
        [
          371.2,
          427.2,
          390.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        49.17,
        [
          364.8,
          0.0,
          505.6,
          230.4
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      16.22
    ],
    "carry_px_err_mean": 127.9,
    "carry_frames": 1045,
    "recovered_after_occlusion": true
  },
  "gate_speed_ms": 2.5,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
