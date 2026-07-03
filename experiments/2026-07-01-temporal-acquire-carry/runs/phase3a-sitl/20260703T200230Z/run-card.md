# Run `20260703T200230Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T20:02:30.497575+00:00
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
    "n_frames": 2972,
    "duration_s": 150.0,
    "achieved_hz": 19.8,
    "carry_fps": 20.4,
    "in_fov_frac": 0.2298,
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
        34.79,
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
          339.2,
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
        41.85,
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
        44.2,
        [
          300.8,
          321.6,
          326.4,
          441.6
        ],
        false,
        "size"
      ],
      [
        46.56,
        [
          307.2,
          268.8,
          326.4,
          379.2
        ],
        false,
        "size"
      ],
      [
        48.91,
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
          38.4
        ],
        false,
        "size"
      ],
      [
        53.52,
        [
          307.2,
          326.4,
          326.4,
          446.4
        ],
        false,
        "size"
      ],
      [
        55.87,
        [
          313.6,
          273.6,
          332.8,
          388.8
        ],
        false,
        "size"
      ],
      [
        58.18,
        [
          345.6,
          0.0,
          358.4,
          105.6
        ],
        false,
        "size"
      ],
      [
        60.48,
        [
          358.4,
          0.0,
          364.8,
          48.0
        ],
        false,
        "size"
      ],
      [
        62.83,
        [
          339.2,
          105.6,
          358.4,
          230.4
        ],
        false,
        "size"
      ],
      [
        65.18,
        [
          332.8,
          48.0,
          371.2,
          172.8
        ],
        false,
        "size"
      ],
      [
        67.54,
        [
          320.0,
          230.4,
          345.6,
          350.4
        ],
        false,
        "size"
      ],
      [
        69.89,
        [
          332.8,
          172.8,
          358.4,
          288.0
        ],
        false,
        "size"
      ],
      [
        72.24,
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
        74.6,
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
        77.0,
        [
          352.0,
          465.6,
          358.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        79.35,
        [
          352.0,
          177.6,
          364.8,
          302.4
        ],
        false,
        "size"
      ],
      [
        81.61,
        [
          364.8,
          0.0,
          377.6,
          14.4
        ],
        false,
        "size"
      ],
      [
        83.96,
        [
          364.8,
          62.4,
          384.0,
          187.2
        ],
        false,
        "size"
      ],
      [
        86.26,
        [
          364.8,
          4.8,
          390.4,
          124.8
        ],
        false,
        "size"
      ],
      [
        88.57,
        [
          371.2,
          0.0,
          390.4,
          72.0
        ],
        false,
        "size"
      ],
      [
        90.92,
        [
          364.8,
          129.6,
          384.0,
          254.4
        ],
        false,
        "size"
      ],
      [
        93.27,
        [
          371.2,
          72.0,
          390.4,
          196.8
        ],
        false,
        "size"
      ],
      [
        95.58,
        [
          377.6,
          19.2,
          396.8,
          139.2
        ],
        false,
        "size"
      ],
      [
        97.83,
        [
          32.0,
          19.2,
          64.0,
          48.0
        ],
        false,
        "size"
      ],
      [
        100.13,
        [
          198.4,
          0.0,
          640.0,
          48.0
        ],
        false,
        "size"
      ],
      [
        102.34,
        [
          44.8,
          48.0,
          57.6,
          57.6
        ],
        false,
        "size"
      ],
      [
        104.49,
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
        106.69,
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
        108.85,
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
        111.05,
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
        113.25,
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
        115.45,
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
        117.61,
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
        119.81,
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
        121.96,
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
        124.12,
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
        126.27,
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
        128.47,
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
        130.63,
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
        132.83,
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
        134.98,
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
        137.14,
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
        139.34,
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
        141.49,
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
        143.69,
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
        145.85,
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
        148.0,
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
    "carry_frames": 470,
    "recovered_after_occlusion": false,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 470,
      "final_d_true_m": 83.5,
      "final_d_dist_m": 58.77,
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
