# Run `20260703T095642Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T09:56:42.375052+00:00
- **git SHA:** `9ea5119609ee714dc2ba3ed2bfc9afff53bc7a31`  ⚠️ DIRTY TREE
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
  "speed": 0.5,
  "duration_s": 75.0,
  "hz": 20,
  "image_size": 1024,
  "sam2": "facebook/sam2.1-hiera-tiny",
  "validate": "sizeprior-0.5-2.0",
  "deadreckon": true,
  "twin": "escort",
  "retarget_t": null,
  "loss_gate": "motion",
  "score_tau": 0.0,
  "dr": "pursuit",
  "acquire_hold": "motion",
  "reground_gate": "none",
  "catchup_replay": true,
  "carry": "host-3090"
}
```

## Results

```json
{
  "trial": {
    "speed_ms": 0.5,
    "image_size": 1024,
    "n_frames": 1444,
    "duration_s": 75.0,
    "achieved_hz": 19.3,
    "carry_fps": 20.3,
    "in_fov_frac": 1.0,
    "first_lock_s": 2.3,
    "n_acquire_attempts": 5,
    "n_rejected_acquires": 3,
    "n_reground_gate_rejects": 0,
    "acquire_log": [
      [
        2.3,
        [
          243.2,
          72.0,
          396.8,
          336.0
        ],
        true,
        ""
      ],
      [
        35.13,
        [
          147.2,
          292.8,
          448.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        37.48,
        [
          294.4,
          384.0,
          313.6,
          470.4
        ],
        false,
        "size"
      ],
      [
        39.79,
        [
          294.4,
          0.0,
          416.0,
          72.0
        ],
        false,
        "size"
      ],
      [
        42.09,
        [
          300.8,
          0.0,
          422.4,
          134.4
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      9.37
    ],
    "carry_px_err_mean": 26.7,
    "carry_frames": 1150,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "escort",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 1150,
      "final_d_true_m": 0.44,
      "final_d_dist_m": 3.63,
      "closest_at_end": "true",
      "relock_on": [
        "true"
      ]
    }
  },
  "gate_speed_ms": 0.5,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
