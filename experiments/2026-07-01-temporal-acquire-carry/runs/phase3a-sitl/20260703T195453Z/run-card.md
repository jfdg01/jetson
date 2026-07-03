# Run `20260703T195453Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T19:54:53.193228+00:00
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
    "n_frames": 2976,
    "duration_s": 150.0,
    "achieved_hz": 19.8,
    "carry_fps": 20.6,
    "in_fov_frac": 0.2305,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 55,
    "n_rejected_acquires": 53,
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
        34.71,
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
        37.06,
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
        39.41,
        [
          307.2,
          216.0,
          332.8,
          331.2
        ],
        false,
        "size"
      ],
      [
        41.76,
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
        44.12,
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
        46.47,
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
        48.82,
        [
          307.2,
          211.2,
          339.2,
          326.4
        ],
        false,
        "size"
      ],
      [
        51.18,
        [
          307.2,
          153.6,
          345.6,
          278.4
        ],
        false,
        "size"
      ],
      [
        53.53,
        [
          307.2,
          100.8,
          352.0,
          220.8
        ],
        false,
        "size"
      ],
      [
        55.83,
        [
          339.2,
          38.4,
          364.8,
          163.2
        ],
        false,
        "size"
      ],
      [
        58.24,
        [
          339.2,
          456.0,
          345.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        60.54,
        [
          352.0,
          0.0,
          364.8,
          52.8
        ],
        false,
        "size"
      ],
      [
        62.89,
        [
          332.8,
          105.6,
          358.4,
          235.2
        ],
        false,
        "size"
      ],
      [
        65.25,
        [
          352.0,
          52.8,
          364.8,
          182.4
        ],
        false,
        "size"
      ],
      [
        67.55,
        [
          345.6,
          0.0,
          371.2,
          115.2
        ],
        false,
        "size"
      ],
      [
        69.85,
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
        72.11,
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
        74.46,
        [
          352.0,
          67.2,
          371.2,
          192.0
        ],
        false,
        "size"
      ],
      [
        76.81,
        [
          332.8,
          244.8,
          358.4,
          355.2
        ],
        false,
        "size"
      ],
      [
        79.22,
        [
          320.0,
          412.8,
          345.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        81.47,
        [
          364.8,
          0.0,
          384.0,
          19.2
        ],
        false,
        "size"
      ],
      [
        83.82,
        [
          358.4,
          81.6,
          377.6,
          206.4
        ],
        false,
        "size"
      ],
      [
        86.13,
        [
          364.8,
          19.2,
          390.4,
          144.0
        ],
        false,
        "size"
      ],
      [
        88.48,
        [
          345.6,
          206.4,
          371.2,
          321.6
        ],
        false,
        "size"
      ],
      [
        90.73,
        [
          377.6,
          0.0,
          390.4,
          28.8
        ],
        false,
        "size"
      ],
      [
        93.09,
        [
          364.8,
          91.2,
          384.0,
          216.0
        ],
        false,
        "size"
      ],
      [
        95.39,
        [
          371.2,
          33.6,
          390.4,
          158.4
        ],
        false,
        "size"
      ],
      [
        97.64,
        [
          371.2,
          0.0,
          396.8,
          100.8
        ],
        false,
        "size"
      ],
      [
        99.84,
        [
          38.4,
          24.0,
          64.0,
          52.8
        ],
        false,
        "size"
      ],
      [
        102.1,
        [
          422.4,
          0.0,
          640.0,
          24.0
        ],
        false,
        "size"
      ],
      [
        104.25,
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
        106.4,
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
        108.56,
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
        110.71,
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
        112.91,
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
        115.07,
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
        117.22,
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
        119.37,
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
        121.52,
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
        123.73,
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
        125.88,
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
        128.08,
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
        130.24,
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
        132.39,
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
        134.54,
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
        136.75,
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
        138.9,
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
        141.1,
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
        143.26,
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
        145.41,
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
        147.61,
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
        149.82,
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
      "final_d_true_m": 82.88,
      "final_d_dist_m": 58.15,
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
