# Run `20260703T161556Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T16:15:56.714217+00:00
- **git SHA:** `c6b4a879cc8fa808e353866c947307e5f5abe62a`  ⚠️ DIRTY TREE
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
  "reground_gate": "mask",
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
    "n_frames": 1462,
    "duration_s": 75.0,
    "achieved_hz": 19.5,
    "carry_fps": 20.6,
    "in_fov_frac": 1.0,
    "first_lock_s": 2.3,
    "n_acquire_attempts": 11,
    "n_rejected_acquires": 8,
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
        35.1,
        [
          147.2,
          297.6,
          448.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        37.46,
        [
          294.4,
          379.2,
          313.6,
          465.6
        ],
        false,
        "size"
      ],
      [
        39.76,
        [
          294.4,
          0.0,
          409.6,
          62.4
        ],
        false,
        "size"
      ],
      [
        42.11,
        [
          0.0,
          81.6,
          633.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        44.42,
        [
          211.2,
          0.0,
          499.2,
          206.4
        ],
        false,
        "size"
      ],
      [
        46.82,
        [
          0.0,
          216.0,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        49.22,
        [
          0.0,
          288.0,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        51.53,
        [
          192.0,
          0.0,
          505.6,
          398.4
        ],
        false,
        "size"
      ],
      [
        53.83,
        [
          294.4,
          0.0,
          416.0,
          225.6
        ],
        true,
        ""
      ],
      [
        56.44,
        [
          441.6,
          139.2,
          595.2,
          384.0
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      21.13,
      2.3
    ],
    "carry_px_err_mean": 29.3,
    "carry_frames": 886,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "escort",
      "id_switch_s": 18.29,
      "frac_box_closer_distractor": 0.406,
      "n_boxed_twin_frames": 886,
      "final_d_true_m": 4.19,
      "final_d_dist_m": 0.42,
      "closest_at_end": "distractor",
      "relock_on": [
        "?",
        "distractor"
      ]
    },
    "retarget": {
      "commanded_t_s": 50.0,
      "fired_t_s": 54.14,
      "caption": "the blue car",
      "switch_walls_s": [
        2.3
      ],
      "switch_on": [
        "distractor"
      ],
      "n_post_boxed_frames": 360,
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
