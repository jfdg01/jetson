# Run `20260703T201007Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T20:10:07.777035+00:00
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
    "n_frames": 2974,
    "duration_s": 150.0,
    "achieved_hz": 19.8,
    "carry_fps": 20.5,
    "in_fov_frac": 0.23,
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
          235.2
        ],
        false,
        "size"
      ],
      [
        39.5,
        [
          300.8,
          211.2,
          332.8,
          331.2
        ],
        false,
        "size"
      ],
      [
        41.81,
        [
          300.8,
          38.4,
          320.0,
          48.0
        ],
        false,
        "size"
      ],
      [
        44.16,
        [
          300.8,
          316.8,
          320.0,
          436.8
        ],
        false,
        "size"
      ],
      [
        46.51,
        [
          300.8,
          268.8,
          326.4,
          379.2
        ],
        false,
        "size"
      ],
      [
        48.87,
        [
          294.4,
          211.2,
          339.2,
          326.4
        ],
        false,
        "size"
      ],
      [
        51.12,
        [
          345.6,
          0.0,
          358.4,
          33.6
        ],
        false,
        "size"
      ],
      [
        53.47,
        [
          307.2,
          321.6,
          326.4,
          441.6
        ],
        false,
        "size"
      ],
      [
        55.83,
        [
          313.6,
          273.6,
          332.8,
          384.0
        ],
        false,
        "size"
      ],
      [
        58.18,
        [
          313.6,
          216.0,
          339.2,
          340.8
        ],
        false,
        "size"
      ],
      [
        60.43,
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
        62.79,
        [
          313.6,
          326.4,
          332.8,
          451.2
        ],
        false,
        "size"
      ],
      [
        65.09,
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
        67.44,
        [
          320.0,
          225.6,
          345.6,
          326.4
        ],
        false,
        "size"
      ],
      [
        69.8,
        [
          332.8,
          168.0,
          352.0,
          292.8
        ],
        false,
        "size"
      ],
      [
        72.15,
        [
          332.8,
          105.6,
          364.8,
          235.2
        ],
        false,
        "size"
      ],
      [
        74.5,
        [
          358.4,
          52.8,
          371.2,
          172.8
        ],
        false,
        "size"
      ],
      [
        76.86,
        [
          332.8,
          235.2,
          352.0,
          345.6
        ],
        false,
        "size"
      ],
      [
        79.16,
        [
          358.4,
          0.0,
          371.2,
          62.4
        ],
        false,
        "size"
      ],
      [
        81.41,
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
        83.77,
        [
          364.8,
          62.4,
          377.6,
          182.4
        ],
        false,
        "size"
      ],
      [
        86.12,
        [
          332.8,
          240.0,
          358.4,
          355.2
        ],
        false,
        "size"
      ],
      [
        88.42,
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
        90.67,
        [
          371.2,
          0.0,
          377.6,
          19.2
        ],
        false,
        "size"
      ],
      [
        92.98,
        [
          364.8,
          76.8,
          384.0,
          201.6
        ],
        false,
        "size"
      ],
      [
        95.28,
        [
          371.2,
          19.2,
          390.4,
          139.2
        ],
        false,
        "size"
      ],
      [
        97.58,
        [
          371.2,
          0.0,
          390.4,
          81.6
        ],
        false,
        "size"
      ],
      [
        99.84,
        [
          44.8,
          48.0,
          64.0,
          67.2
        ],
        false,
        "size"
      ],
      [
        102.09,
        [
          44.8,
          48.0,
          64.0,
          67.2
        ],
        false,
        "size"
      ],
      [
        104.29,
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
        106.45,
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
        108.6,
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
        110.75,
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
        112.96,
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
        115.16,
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
        117.31,
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
        119.51,
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
        126.07,
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
        128.23,
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
        136.94,
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
        141.3,
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
        143.5,
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
        147.8,
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
    "carry_frames": 472,
    "recovered_after_occlusion": false,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 472,
      "final_d_true_m": 83.62,
      "final_d_dist_m": 58.89,
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
