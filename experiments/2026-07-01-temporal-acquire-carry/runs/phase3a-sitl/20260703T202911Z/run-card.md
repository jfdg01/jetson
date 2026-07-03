# Run `20260703T202911Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T20:29:11.059480+00:00
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
  "reground_hold": "chase",
  "reground_gate": "mask",
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
    "n_frames": 2973,
    "duration_s": 150.0,
    "achieved_hz": 19.8,
    "carry_fps": 20.4,
    "in_fov_frac": 0.2297,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 54,
    "n_rejected_acquires": 52,
    "n_reground_gate_rejects": 0,
    "app_template": [
      245.0,
      245.0,
      245.0
    ],
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
        34.72,
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
        37.07,
        [
          313.6,
          124.8,
          339.2,
          240.0
        ],
        false,
        "size"
      ],
      [
        39.42,
        [
          300.8,
          216.0,
          332.8,
          336.0
        ],
        false,
        "size"
      ],
      [
        41.78,
        [
          300.8,
          153.6,
          345.6,
          273.6
        ],
        false,
        "size"
      ],
      [
        44.13,
        [
          300.8,
          321.6,
          320.0,
          441.6
        ],
        false,
        "size"
      ],
      [
        46.48,
        [
          307.2,
          268.8,
          326.4,
          384.0
        ],
        false,
        "size"
      ],
      [
        48.84,
        [
          307.2,
          211.2,
          332.8,
          326.4
        ],
        false,
        "size"
      ],
      [
        51.19,
        [
          313.6,
          158.4,
          345.6,
          278.4
        ],
        false,
        "size"
      ],
      [
        53.54,
        [
          307.2,
          96.0,
          352.0,
          220.8
        ],
        false,
        "size"
      ],
      [
        55.9,
        [
          307.2,
          268.8,
          332.8,
          388.8
        ],
        false,
        "size"
      ],
      [
        58.25,
        [
          307.2,
          216.0,
          345.6,
          336.0
        ],
        false,
        "size"
      ],
      [
        60.5,
        [
          352.0,
          0.0,
          358.4,
          38.4
        ],
        false,
        "size"
      ],
      [
        62.86,
        [
          307.2,
          321.6,
          332.8,
          451.2
        ],
        false,
        "size"
      ],
      [
        65.16,
        [
          345.6,
          43.2,
          364.8,
          168.0
        ],
        false,
        "size"
      ],
      [
        67.56,
        [
          345.6,
          465.6,
          352.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        69.97,
        [
          320.0,
          393.6,
          339.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        72.32,
        [
          339.2,
          105.6,
          364.8,
          230.4
        ],
        false,
        "size"
      ],
      [
        74.67,
        [
          352.0,
          48.0,
          371.2,
          172.8
        ],
        false,
        "size"
      ],
      [
        77.07,
        [
          345.6,
          460.8,
          358.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        79.38,
        [
          364.8,
          0.0,
          377.6,
          57.6
        ],
        false,
        "size"
      ],
      [
        81.73,
        [
          326.4,
          110.4,
          371.2,
          240.0
        ],
        false,
        "size"
      ],
      [
        84.08,
        [
          358.4,
          52.8,
          377.6,
          177.6
        ],
        false,
        "size"
      ],
      [
        86.44,
        [
          339.2,
          235.2,
          358.4,
          345.6
        ],
        false,
        "size"
      ],
      [
        88.74,
        [
          371.2,
          14.4,
          377.6,
          62.4
        ],
        false,
        "size"
      ],
      [
        90.99,
        [
          364.8,
          0.0,
          371.2,
          14.4
        ],
        false,
        "size"
      ],
      [
        93.35,
        [
          364.8,
          62.4,
          377.6,
          187.2
        ],
        false,
        "size"
      ],
      [
        95.65,
        [
          364.8,
          9.6,
          390.4,
          124.8
        ],
        false,
        "size"
      ],
      [
        97.95,
        [
          371.2,
          0.0,
          384.0,
          67.2
        ],
        false,
        "size"
      ],
      [
        100.16,
        [
          256.0,
          0.0,
          281.6,
          19.2
        ],
        false,
        "size"
      ],
      [
        102.31,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        104.51,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        106.72,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        108.87,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        111.02,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        113.23,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        115.43,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        117.63,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        119.78,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        121.94,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        124.14,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        126.29,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        128.45,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        130.6,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        132.8,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        135.01,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        137.16,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        139.31,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        141.52,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        143.67,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        145.87,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        148.08,
        [
          44.8,
          24.0,
          64.0,
          33.6
        ],
        false,
        "size"
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [],
    "carry_px_err_mean": 8.6,
    "carry_frames": 469,
    "recovered_after_occlusion": false,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 469,
      "final_d_true_m": 83.68,
      "final_d_dist_m": 58.94,
      "final_d_dist2_m": null,
      "closest_at_end": "distractor",
      "relock_on": []
    }
  },
  "gate_speed_ms": 0.25,
  "gate": "FAIL"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
