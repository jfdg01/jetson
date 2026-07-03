# Run `20260703T155649Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T15:56:49.583000+00:00
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
    "n_frames": 2944,
    "duration_s": 150.0,
    "achieved_hz": 19.6,
    "carry_fps": 20.5,
    "in_fov_frac": 0.4467,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 42,
    "n_rejected_acquires": 35,
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
        34.81,
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
        37.16,
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
        39.42,
        [
          300.8,
          0.0,
          403.2,
          28.8
        ],
        false,
        "size"
      ],
      [
        41.72,
        [
          281.6,
          0.0,
          403.2,
          81.6
        ],
        false,
        "size"
      ],
      [
        44.02,
        [
          204.8,
          0.0,
          403.2,
          96.0
        ],
        false,
        "size"
      ],
      [
        46.33,
        [
          275.2,
          0.0,
          396.8,
          124.8
        ],
        true,
        ""
      ],
      [
        56.08,
        [
          249.6,
          0.0,
          396.8,
          268.8
        ],
        true,
        ""
      ],
      [
        61.61,
        [
          243.2,
          0.0,
          390.4,
          249.6
        ],
        true,
        ""
      ],
      [
        67.28,
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
        69.58,
        [
          243.2,
          0.0,
          390.4,
          254.4
        ],
        true,
        ""
      ],
      [
        75.22,
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
        77.62,
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
        80.02,
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
        82.43,
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
        84.83,
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
        87.23,
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
        89.64,
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
        92.04,
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
        94.44,
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
        96.85,
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
        99.25,
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
        101.65,
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
        104.06,
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
        106.46,
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
        108.86,
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
        111.27,
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
        113.67,
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
        116.07,
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
        118.48,
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
        120.88,
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
        123.28,
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
        125.69,
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
        128.09,
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
        130.4,
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
        136.04,
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
        140.85,
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
        143.25,
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
        148.01,
        [
          0.0,
          201.6,
          64.0,
          480.0
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 6,
    "relock_walls_s": [
      13.87,
      2.34,
      2.3,
      4.71,
      57.58,
      14.37
    ],
    "carry_px_err_mean": 18.7,
    "carry_frames": 554,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 83.58,
      "frac_box_closer_distractor": 0.141,
      "n_boxed_twin_frames": 554,
      "final_d_true_m": 26.68,
      "final_d_dist_m": 1.95,
      "closest_at_end": "distractor",
      "relock_on": [
        "true",
        "distractor",
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
