# Run `20260703T194557Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T19:45:57.150899+00:00
- **git SHA:** `727025427f55acb95d5a413ec4fad9e8d612384b`  ⚠️ DIRTY TREE
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
  "speed": 0.25,
  "duration_s": 150.0,
  "hz": 20,
  "image_size": 1024,
  "sam2": "facebook/sam2.1-hiera-tiny",
  "validate": "sizeprior-0.5-2.0",
  "deadreckon": true,
  "twin": "decoy",
  "retarget_t": null,
  "loss_gate": "motion",
  "score_tau": 0.0,
  "dr": "pursuit",
  "acquire_hold": "motion",
  "reground_hold": "none",
  "reground_gate": "none",
  "vmax": 2.5,
  "acquire_delay": 0.0,
  "app_tau": 12.0,
  "decoy_shade": 215,
  "decoy2_m": null,
  "occ2": null,
  "catchup_replay": true,
  "carry": "host-3090"
}
```

## Results

```json
{
  "trial": {
    "speed_ms": 0.25,
    "image_size": 1024,
    "n_frames": 2963,
    "duration_s": 150.0,
    "achieved_hz": 19.8,
    "carry_fps": 20.8,
    "in_fov_frac": 0.4472,
    "first_lock_s": 2.3,
    "n_acquire_attempts": 42,
    "n_rejected_acquires": 36,
    "n_reground_gate_rejects": 0,
    "app_template": null,
    "acquire_log": [
      [
        2.3,
        [
          243.2,
          72.0,
          396.8,
          340.8
        ],
        true,
        ""
      ],
      [
        34.69,
        [
          294.4,
          273.6,
          313.6,
          384.0
        ],
        false,
        "size"
      ],
      [
        37.04,
        [
          294.4,
          307.2,
          313.6,
          417.6
        ],
        false,
        "size"
      ],
      [
        39.29,
        [
          198.4,
          0.0,
          416.0,
          28.8
        ],
        false,
        "size"
      ],
      [
        41.6,
        [
          288.0,
          0.0,
          409.6,
          67.2
        ],
        false,
        "size"
      ],
      [
        43.9,
        [
          204.8,
          0.0,
          486.4,
          96.0
        ],
        false,
        "size"
      ],
      [
        46.2,
        [
          204.8,
          0.0,
          416.0,
          124.8
        ],
        true,
        ""
      ],
      [
        59.22,
        [
          243.2,
          0.0,
          390.4,
          278.4
        ],
        true,
        ""
      ],
      [
        64.79,
        [
          243.2,
          0.0,
          384.0,
          249.6
        ],
        true,
        ""
      ],
      [
        70.43,
        [
          0.0,
          206.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        72.83,
        [
          0.0,
          201.6,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        75.24,
        [
          0.0,
          201.6,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        77.64,
        [
          0.0,
          196.8,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        80.04,
        [
          0.0,
          196.8,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        82.45,
        [
          0.0,
          201.6,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        84.85,
        [
          0.0,
          201.6,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        87.25,
        [
          0.0,
          196.8,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        89.66,
        [
          0.0,
          201.6,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        92.06,
        [
          0.0,
          196.8,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        94.46,
        [
          0.0,
          196.8,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        96.87,
        [
          0.0,
          201.6,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        99.27,
        [
          0.0,
          201.6,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        101.67,
        [
          0.0,
          196.8,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        104.08,
        [
          0.0,
          196.8,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        106.48,
        [
          0.0,
          196.8,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        108.88,
        [
          0.0,
          196.8,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        111.29,
        [
          0.0,
          196.8,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        113.59,
        [
          243.2,
          0.0,
          390.4,
          240.0
        ],
        true,
        ""
      ],
      [
        119.23,
        [
          0.0,
          206.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        121.63,
        [
          0.0,
          211.2,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        124.03,
        [
          0.0,
          206.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        126.44,
        [
          0.0,
          206.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        128.84,
        [
          0.0,
          206.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        131.24,
        [
          0.0,
          206.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        133.65,
        [
          0.0,
          206.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        136.05,
        [
          0.0,
          206.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        138.45,
        [
          0.0,
          201.6,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        140.86,
        [
          0.0,
          206.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        143.26,
        [
          0.0,
          201.6,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        145.66,
        [
          0.0,
          201.6,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        148.07,
        [
          0.0,
          201.6,
          640.0,
          480.0
        ],
        false,
        "size"
      ]
    ],
    "n_regrounds": 5,
    "relock_walls_s": [
      13.87,
      2.31,
      2.31,
      45.57
    ],
    "carry_px_err_mean": 23.3,
    "carry_frames": 675,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 54.34,
      "frac_box_closer_distractor": 0.119,
      "n_boxed_twin_frames": 675,
      "final_d_true_m": 26.69,
      "final_d_dist_m": 1.96,
      "final_d_dist2_m": null,
      "closest_at_end": "distractor",
      "relock_on": [
        "true",
        "distractor",
        "distractor",
        "distractor"
      ]
    }
  },
  "gate_speed_ms": 0.25,
  "gate": "FAIL"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
