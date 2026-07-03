# Run `20260703T164856Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T16:48:56.132564+00:00
- **git SHA:** `59c1d1a3bd2af0c5791695b7cd9708e4c547602c`  ⚠️ DIRTY TREE
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
  "reground_gate": "none",
  "vmax": 2.5,
  "acquire_delay": 0.0,
  "app_tau": 12.0,
  "decoy_shade": 215,
  "decoy2_m": 7.0,
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
    "n_frames": 2917,
    "duration_s": 150.0,
    "achieved_hz": 19.4,
    "carry_fps": 20.6,
    "in_fov_frac": 0.4501,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 35,
    "n_rejected_acquires": 22,
    "n_reground_gate_rejects": 0,
    "app_template": null,
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
        4.71,
        [
          249.6,
          96.0,
          390.4,
          340.8
        ],
        true,
        ""
      ],
      [
        34.75,
        [
          294.4,
          273.6,
          313.6,
          379.2
        ],
        false,
        "size"
      ],
      [
        37.1,
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
        39.45,
        [
          147.2,
          321.6,
          448.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        41.76,
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
        44.06,
        [
          204.8,
          0.0,
          486.4,
          100.8
        ],
        false,
        "size"
      ],
      [
        46.36,
        [
          204.8,
          0.0,
          499.2,
          124.8
        ],
        false,
        "size"
      ],
      [
        48.67,
        [
          204.8,
          0.0,
          422.4,
          163.2
        ],
        true,
        ""
      ],
      [
        58.64,
        [
          211.2,
          0.0,
          422.4,
          302.4
        ],
        true,
        ""
      ],
      [
        64.22,
        [
          198.4,
          0.0,
          499.2,
          259.2
        ],
        false,
        "size"
      ],
      [
        66.53,
        [
          288.0,
          0.0,
          422.4,
          249.6
        ],
        true,
        ""
      ],
      [
        72.05,
        [
          243.2,
          4.8,
          390.4,
          249.6
        ],
        true,
        ""
      ],
      [
        77.73,
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
        80.04,
        [
          236.8,
          4.8,
          377.6,
          244.8
        ],
        true,
        ""
      ],
      [
        85.57,
        [
          243.2,
          4.8,
          377.6,
          249.6
        ],
        true,
        ""
      ],
      [
        91.2,
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
        93.5,
        [
          243.2,
          4.8,
          377.6,
          249.6
        ],
        true,
        ""
      ],
      [
        99.14,
        [
          0.0,
          206.4,
          633.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        101.54,
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
        103.94,
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
        106.35,
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
        108.75,
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
        111.1,
        [
          0.0,
          201.6,
          64.0,
          480.0
        ],
        true,
        ""
      ],
      [
        116.53,
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
        118.93,
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
        121.23,
        [
          224.0,
          0.0,
          364.8,
          244.8
        ],
        true,
        ""
      ],
      [
        126.85,
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
        129.21,
        [
          0.0,
          201.6,
          633.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        131.61,
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
        133.91,
        [
          243.2,
          4.8,
          377.6,
          249.6
        ],
        true,
        ""
      ],
      [
        139.54,
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
        141.84,
        [
          243.2,
          4.8,
          390.4,
          254.4
        ],
        true,
        ""
      ],
      [
        147.51,
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
        149.82,
        [
          243.2,
          4.8,
          390.4,
          254.4
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 12,
    "relock_walls_s": [
      16.28,
      2.31,
      4.61,
      2.3,
      4.71,
      2.3,
      4.71,
      14.32,
      7.11,
      9.46,
      4.71,
      4.71
    ],
    "carry_px_err_mean": 18.9,
    "carry_frames": 559,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 83.2,
      "frac_box_closer_distractor": 0.054,
      "n_boxed_twin_frames": 559,
      "final_d_true_m": 26.64,
      "final_d_dist_m": 1.95,
      "final_d_dist2_m": 8.93,
      "closest_at_end": "distractor",
      "relock_on": [
        "true",
        "distractor",
        "distractor",
        "distractor",
        "distractor",
        "distractor",
        "distractor",
        "?",
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
