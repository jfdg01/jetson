# Run `20260703T104124Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T10:41:24.160030+00:00
- **git SHA:** `795975c39a68fe4e38a6cfb1f0023841632ae49e`  ⚠️ DIRTY TREE
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
  "speed": 2.0,
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
  "acquire_hold": "motion",
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
    "speed_ms": 2.0,
    "image_size": 1024,
    "n_frames": 1470,
    "duration_s": 75.0,
    "achieved_hz": 19.6,
    "carry_fps": 20.7,
    "in_fov_frac": 1.0,
    "first_lock_s": 2.3,
    "n_acquire_attempts": 7,
    "n_rejected_acquires": 5,
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
        35.12,
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
        37.37,
        [
          403.2,
          0.0,
          448.0,
          24.0
        ],
        false,
        "size"
      ],
      [
        39.67,
        [
          224.0,
          0.0,
          531.2,
          302.4
        ],
        false,
        "size"
      ],
      [
        42.08,
        [
          345.6,
          456.0,
          358.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        44.43,
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
        46.73,
        [
          352.0,
          0.0,
          480.0,
          235.2
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      13.82
    ],
    "carry_px_err_mean": 102.1,
    "carry_frames": 1087,
    "recovered_after_occlusion": true
  },
  "gate_speed_ms": 2.0,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
