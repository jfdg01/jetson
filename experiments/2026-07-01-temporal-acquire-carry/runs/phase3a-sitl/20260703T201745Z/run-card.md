# Run `20260703T201745Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T20:17:45.056528+00:00
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
    "n_frames": 2966,
    "duration_s": 150.0,
    "achieved_hz": 19.8,
    "carry_fps": 20.1,
    "in_fov_frac": 0.2279,
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
          345.6
        ],
        true,
        ""
      ],
      [
        34.8,
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
        37.15,
        [
          313.6,
          120.0,
          332.8,
          240.0
        ],
        false,
        "size"
      ],
      [
        39.5,
        [
          307.2,
          211.2,
          332.8,
          331.2
        ],
        false,
        "size"
      ],
      [
        41.86,
        [
          300.8,
          148.8,
          345.6,
          273.6
        ],
        false,
        "size"
      ],
      [
        44.21,
        [
          300.8,
          321.6,
          326.4,
          436.8
        ],
        false,
        "size"
      ],
      [
        46.56,
        [
          307.2,
          268.8,
          332.8,
          384.0
        ],
        false,
        "size"
      ],
      [
        48.92,
        [
          307.2,
          211.2,
          339.2,
          331.2
        ],
        false,
        "size"
      ],
      [
        51.17,
        [
          345.6,
          0.0,
          358.4,
          43.2
        ],
        false,
        "size"
      ],
      [
        53.52,
        [
          307.2,
          105.6,
          352.0,
          225.6
        ],
        false,
        "size"
      ],
      [
        55.88,
        [
          313.6,
          278.4,
          332.8,
          393.6
        ],
        false,
        "size"
      ],
      [
        58.28,
        [
          339.2,
          465.6,
          345.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        60.58,
        [
          352.0,
          0.0,
          364.8,
          57.6
        ],
        false,
        "size"
      ],
      [
        62.84,
        [
          358.4,
          0.0,
          364.8,
          14.4
        ],
        false,
        "size"
      ],
      [
        65.19,
        [
          352.0,
          62.4,
          364.8,
          182.4
        ],
        false,
        "size"
      ],
      [
        67.49,
        [
          352.0,
          14.4,
          364.8,
          124.8
        ],
        false,
        "size"
      ],
      [
        69.8,
        [
          358.4,
          0.0,
          371.2,
          76.8
        ],
        false,
        "size"
      ],
      [
        72.15,
        [
          332.8,
          134.4,
          364.8,
          254.4
        ],
        false,
        "size"
      ],
      [
        74.5,
        [
          352.0,
          76.8,
          371.2,
          201.6
        ],
        false,
        "size"
      ],
      [
        76.8,
        [
          358.4,
          19.2,
          377.6,
          139.2
        ],
        false,
        "size"
      ],
      [
        79.16,
        [
          345.6,
          206.4,
          358.4,
          316.8
        ],
        false,
        "size"
      ],
      [
        81.41,
        [
          371.2,
          0.0,
          384.0,
          33.6
        ],
        false,
        "size"
      ],
      [
        83.76,
        [
          358.4,
          91.2,
          377.6,
          216.0
        ],
        false,
        "size"
      ],
      [
        86.07,
        [
          371.2,
          38.4,
          390.4,
          163.2
        ],
        false,
        "size"
      ],
      [
        88.42,
        [
          345.6,
          220.8,
          371.2,
          336.0
        ],
        false,
        "size"
      ],
      [
        90.67,
        [
          377.6,
          0.0,
          390.4,
          43.2
        ],
        false,
        "size"
      ],
      [
        93.03,
        [
          364.8,
          110.4,
          384.0,
          235.2
        ],
        false,
        "size"
      ],
      [
        95.38,
        [
          371.2,
          52.8,
          390.4,
          177.6
        ],
        false,
        "size"
      ],
      [
        97.68,
        [
          243.2,
          0.0,
          537.6,
          134.4
        ],
        false,
        "size"
      ],
      [
        99.94,
        [
          32.0,
          48.0,
          64.0,
          72.0
        ],
        false,
        "size"
      ],
      [
        102.19,
        [
          294.4,
          0.0,
          640.0,
          28.8
        ],
        false,
        "size"
      ],
      [
        104.39,
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
        106.55,
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
        108.7,
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
        110.9,
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
        113.05,
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
        115.21,
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
        117.36,
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
        119.56,
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
        121.72,
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
        123.87,
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
        126.02,
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
        128.18,
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
        130.38,
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
        132.58,
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
        134.79,
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
        136.99,
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
        139.14,
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
        141.29,
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
        143.45,
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
        145.65,
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
        147.85,
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
    "carry_frames": 465,
    "recovered_after_occlusion": false,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 465,
      "final_d_true_m": 82.34,
      "final_d_dist_m": 57.61,
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
