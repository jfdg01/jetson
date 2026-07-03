# Run `20260703T152031Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T15:20:31.504839+00:00
- **git SHA:** `69691e9eaef23ad2cd1ed128149936cec9e045b5`  ⚠️ DIRTY TREE
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
  "retarget_t": 50.0,
  "loss_gate": "motion",
  "score_tau": 0.0,
  "dr": "pursuit",
  "acquire_hold": "motion",
  "reground_gate": "appearance",
  "vmax": 2.5,
  "acquire_delay": 0.0,
  "app_tau": 12.0,
  "decoy_shade": 245,
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
    "n_frames": 1450,
    "duration_s": 75.0,
    "achieved_hz": 19.3,
    "carry_fps": 20.4,
    "in_fov_frac": 1.0,
    "first_lock_s": 2.3,
    "n_acquire_attempts": 6,
    "n_rejected_acquires": 3,
    "n_reground_gate_rejects": 0,
    "app_template": [
      230.0,
      90.0,
      40.0
    ],
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
        35.09,
        [
          147.2,
          288.0,
          448.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        37.44,
        [
          300.8,
          384.0,
          313.6,
          470.4
        ],
        false,
        "size"
      ],
      [
        39.74,
        [
          300.8,
          14.4,
          416.0,
          67.2
        ],
        false,
        "size"
      ],
      [
        42.05,
        [
          300.8,
          0.0,
          422.4,
          129.6
        ],
        true,
        ""
      ],
      [
        52.36,
        [
          403.2,
          254.4,
          544.0,
          480.0
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      9.37,
      2.35
    ],
    "carry_px_err_mean": 30.8,
    "carry_frames": 1109,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "escort",
      "id_switch_s": 22.34,
      "frac_box_closer_distractor": 0.396,
      "n_boxed_twin_frames": 1109,
      "final_d_true_m": 4.18,
      "final_d_dist_m": 0.42,
      "closest_at_end": "distractor",
      "relock_on": [
        "true",
        "distractor"
      ]
    },
    "retarget": {
      "commanded_t_s": 50.0,
      "fired_t_s": 50.01,
      "caption": "the blue car",
      "switch_walls_s": [
        2.35
      ],
      "switch_on": [
        "distractor"
      ],
      "n_post_boxed_frames": 439,
      "frac_box_closer_dist_post": 1.0,
      "dist_in_fov_frac_post": 1.0
    }
  },
  "gate_speed_ms": 0.5,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
