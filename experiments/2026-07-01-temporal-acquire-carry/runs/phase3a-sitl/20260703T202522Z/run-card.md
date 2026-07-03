# Run `20260703T202522Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T20:25:22.373135+00:00
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
    "n_frames": 2978,
    "duration_s": 150.0,
    "achieved_hz": 19.9,
    "carry_fps": 20.7,
    "in_fov_frac": 0.2304,
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
          340.8
        ],
        true,
        ""
      ],
      [
        34.74,
        [
          294.4,
          268.8,
          313.6,
          379.2
        ],
        false,
        "size"
      ],
      [
        37.09,
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
        39.44,
        [
          300.8,
          201.6,
          332.8,
          326.4
        ],
        false,
        "size"
      ],
      [
        41.8,
        [
          300.8,
          144.0,
          352.0,
          268.8
        ],
        false,
        "size"
      ],
      [
        44.15,
        [
          300.8,
          307.2,
          332.8,
          436.8
        ],
        false,
        "size"
      ],
      [
        46.5,
        [
          307.2,
          264.0,
          332.8,
          379.2
        ],
        false,
        "size"
      ],
      [
        48.91,
        [
          294.4,
          436.8,
          307.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        51.16,
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
        53.51,
        [
          307.2,
          326.4,
          332.8,
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
        58.17,
        [
          339.2,
          0.0,
          358.4,
          100.8
        ],
        false,
        "size"
      ],
      [
        60.47,
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
        62.82,
        [
          320.0,
          105.6,
          364.8,
          225.6
        ],
        false,
        "size"
      ],
      [
        65.18,
        [
          345.6,
          48.0,
          371.2,
          168.0
        ],
        false,
        "size"
      ],
      [
        67.58,
        [
          320.0,
          465.6,
          332.8,
          480.0
        ],
        false,
        "size"
      ],
      [
        69.88,
        [
          358.4,
          0.0,
          371.2,
          52.8
        ],
        false,
        "size"
      ],
      [
        72.24,
        [
          320.0,
          110.4,
          371.2,
          240.0
        ],
        false,
        "size"
      ],
      [
        74.59,
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
        76.94,
        [
          332.8,
          235.2,
          358.4,
          345.6
        ],
        false,
        "size"
      ],
      [
        79.3,
        [
          345.6,
          182.4,
          364.8,
          302.4
        ],
        false,
        "size"
      ],
      [
        81.55,
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
        83.9,
        [
          364.8,
          67.2,
          384.0,
          192.0
        ],
        false,
        "size"
      ],
      [
        86.21,
        [
          364.8,
          9.6,
          390.4,
          129.6
        ],
        false,
        "size"
      ],
      [
        88.51,
        [
          377.6,
          0.0,
          390.4,
          72.0
        ],
        false,
        "size"
      ],
      [
        90.76,
        [
          377.6,
          0.0,
          390.4,
          24.0
        ],
        false,
        "size"
      ],
      [
        93.12,
        [
          364.8,
          81.6,
          390.4,
          201.6
        ],
        false,
        "size"
      ],
      [
        95.42,
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
        97.67,
        [
          377.6,
          0.0,
          403.2,
          86.4
        ],
        false,
        "size"
      ],
      [
        99.93,
        [
          44.8,
          24.0,
          64.0,
          48.0
        ],
        false,
        "size"
      ],
      [
        102.13,
        [
          44.8,
          24.0,
          64.0,
          48.0
        ],
        false,
        "size"
      ],
      [
        104.28,
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
        106.44,
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
        108.59,
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
        110.74,
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
        112.89,
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
        115.05,
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
        117.2,
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
        119.35,
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
        121.56,
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
        123.76,
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
        125.96,
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
        128.17,
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
        130.32,
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
        132.52,
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
        134.73,
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
        136.93,
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
        139.08,
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
        141.24,
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
        143.44,
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
        145.59,
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
        147.74,
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
        149.95,
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
    "carry_frames": 474,
    "recovered_after_occlusion": false,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 474,
      "final_d_true_m": 83.27,
      "final_d_dist_m": 58.53,
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
