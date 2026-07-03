# Run `20260703T202133Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T20:21:33.789340+00:00
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
    "n_frames": 2965,
    "duration_s": 150.0,
    "achieved_hz": 19.8,
    "carry_fps": 20.0,
    "in_fov_frac": 0.228,
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
        34.82,
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
        37.17,
        [
          313.6,
          124.8,
          332.8,
          240.0
        ],
        false,
        "size"
      ],
      [
        39.52,
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
        41.93,
        [
          294.4,
          384.0,
          313.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        44.28,
        [
          300.8,
          326.4,
          320.0,
          446.4
        ],
        false,
        "size"
      ],
      [
        46.63,
        [
          307.2,
          273.6,
          332.8,
          388.8
        ],
        false,
        "size"
      ],
      [
        48.99,
        [
          300.8,
          220.8,
          332.8,
          340.8
        ],
        false,
        "size"
      ],
      [
        51.34,
        [
          307.2,
          168.0,
          352.0,
          297.6
        ],
        false,
        "size"
      ],
      [
        53.69,
        [
          307.2,
          110.4,
          352.0,
          235.2
        ],
        false,
        "size"
      ],
      [
        56.05,
        [
          307.2,
          288.0,
          332.8,
          408.0
        ],
        false,
        "size"
      ],
      [
        58.45,
        [
          307.2,
          465.6,
          320.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        60.75,
        [
          345.6,
          0.0,
          358.4,
          67.2
        ],
        false,
        "size"
      ],
      [
        63.11,
        [
          332.8,
          129.6,
          358.4,
          254.4
        ],
        false,
        "size"
      ],
      [
        65.46,
        [
          339.2,
          76.8,
          364.8,
          196.8
        ],
        false,
        "size"
      ],
      [
        67.76,
        [
          352.0,
          19.2,
          364.8,
          139.2
        ],
        false,
        "size"
      ],
      [
        70.12,
        [
          332.8,
          206.4,
          352.0,
          321.6
        ],
        false,
        "size"
      ],
      [
        72.37,
        [
          358.4,
          0.0,
          371.2,
          33.6
        ],
        false,
        "size"
      ],
      [
        74.72,
        [
          332.8,
          96.0,
          364.8,
          220.8
        ],
        false,
        "size"
      ],
      [
        77.03,
        [
          352.0,
          38.4,
          371.2,
          163.2
        ],
        false,
        "size"
      ],
      [
        79.38,
        [
          332.8,
          225.6,
          352.0,
          336.0
        ],
        false,
        "size"
      ],
      [
        81.68,
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
        83.93,
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
        86.29,
        [
          358.4,
          62.4,
          377.6,
          187.2
        ],
        false,
        "size"
      ],
      [
        88.59,
        [
          364.8,
          9.6,
          384.0,
          129.6
        ],
        false,
        "size"
      ],
      [
        90.89,
        [
          364.8,
          0.0,
          384.0,
          76.8
        ],
        false,
        "size"
      ],
      [
        93.15,
        [
          371.2,
          0.0,
          384.0,
          24.0
        ],
        false,
        "size"
      ],
      [
        95.5,
        [
          364.8,
          86.4,
          384.0,
          211.2
        ],
        false,
        "size"
      ],
      [
        97.8,
        [
          371.2,
          28.8,
          390.4,
          153.6
        ],
        false,
        "size"
      ],
      [
        100.11,
        [
          371.2,
          0.0,
          390.4,
          96.0
        ],
        false,
        "size"
      ],
      [
        102.36,
        [
          371.2,
          0.0,
          396.8,
          43.2
        ],
        false,
        "size"
      ],
      [
        104.56,
        [
          422.4,
          0.0,
          518.4,
          24.0
        ],
        false,
        "size"
      ],
      [
        106.77,
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
        108.92,
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
        111.12,
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
        113.28,
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
        115.48,
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
        119.79,
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
        126.34,
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
        128.5,
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
        130.65,
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
        132.85,
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
        135.06,
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
        137.26,
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
        139.41,
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
        141.57,
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
        143.72,
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
        148.03,
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
    "carry_frames": 464,
    "recovered_after_occlusion": false,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 464,
      "final_d_true_m": 81.2,
      "final_d_dist_m": 56.46,
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
