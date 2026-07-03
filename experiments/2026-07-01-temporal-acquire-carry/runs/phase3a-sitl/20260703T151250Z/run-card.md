# Run `20260703T151250Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T15:12:50.282243+00:00
- **git SHA:** `69691e9eaef23ad2cd1ed128149936cec9e045b5`  ⚠️ DIRTY TREE
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
  "reground_gate": "appearance",
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
    "n_frames": 2964,
    "duration_s": 150.0,
    "achieved_hz": 19.8,
    "carry_fps": 20.4,
    "in_fov_frac": 0.4895,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 49,
    "n_rejected_acquires": 32,
    "n_reground_gate_rejects": 14,
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
        34.75,
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
        37.11,
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
        39.46,
        [
          153.6,
          321.6,
          454.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        41.76,
        [
          294.4,
          0.0,
          409.6,
          72.0
        ],
        false,
        "size"
      ],
      [
        44.07,
        [
          211.2,
          0.0,
          492.8,
          100.8
        ],
        false,
        "size"
      ],
      [
        46.37,
        [
          204.8,
          0.0,
          499.2,
          115.2
        ],
        false,
        "size"
      ],
      [
        48.67,
        [
          211.2,
          0.0,
          499.2,
          172.8
        ],
        false,
        "size"
      ],
      [
        51.08,
        [
          0.0,
          144.0,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        53.48,
        [
          0.0,
          177.6,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        55.78,
        [
          281.6,
          9.6,
          409.6,
          264.0
        ],
        false,
        "gate"
      ],
      [
        58.09,
        [
          275.2,
          0.0,
          409.6,
          292.8
        ],
        false,
        "gate"
      ],
      [
        60.39,
        [
          192.0,
          0.0,
          505.6,
          331.2
        ],
        false,
        "size"
      ],
      [
        62.69,
        [
          198.4,
          0.0,
          505.6,
          355.2
        ],
        false,
        "size"
      ],
      [
        65.0,
        [
          268.8,
          0.0,
          428.8,
          384.0
        ],
        false,
        "gate"
      ],
      [
        67.3,
        [
          268.8,
          0.0,
          428.8,
          412.8
        ],
        true,
        ""
      ],
      [
        77.15,
        [
          236.8,
          52.8,
          371.2,
          288.0
        ],
        false,
        "gate"
      ],
      [
        79.56,
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
        81.86,
        [
          230.4,
          4.8,
          371.2,
          240.0
        ],
        false,
        "gate"
      ],
      [
        84.26,
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
        86.67,
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
        89.07,
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
        91.48,
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
        93.88,
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
        96.28,
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
        98.68,
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
        101.09,
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
        103.49,
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
        105.9,
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
        108.3,
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
        110.7,
        [
          0.0,
          192.0,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        113.11,
        [
          0.0,
          192.0,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        115.51,
        [
          0.0,
          192.0,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        117.81,
        [
          230.4,
          0.0,
          371.2,
          230.4
        ],
        false,
        "gate"
      ],
      [
        120.22,
        [
          0.0,
          192.0,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        122.52,
        [
          230.4,
          0.0,
          371.2,
          235.2
        ],
        false,
        "gate"
      ],
      [
        124.82,
        [
          236.8,
          0.0,
          371.2,
          230.4
        ],
        false,
        "gate"
      ],
      [
        127.12,
        [
          236.8,
          0.0,
          371.2,
          225.6
        ],
        false,
        "gate"
      ],
      [
        129.53,
        [
          0.0,
          192.0,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        131.83,
        [
          236.8,
          0.0,
          371.2,
          225.6
        ],
        false,
        "gate"
      ],
      [
        134.23,
        [
          0.0,
          192.0,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        136.54,
        [
          236.8,
          0.0,
          377.6,
          225.6
        ],
        false,
        "gate"
      ],
      [
        138.84,
        [
          236.8,
          0.0,
          371.2,
          230.4
        ],
        false,
        "gate"
      ],
      [
        141.14,
        [
          230.4,
          0.0,
          371.2,
          220.8
        ],
        false,
        "gate"
      ],
      [
        143.45,
        [
          230.4,
          0.0,
          371.2,
          225.6
        ],
        false,
        "gate"
      ],
      [
        145.85,
        [
          0.0,
          192.0,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        148.26,
        [
          0.0,
          182.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ]
    ],
    "n_regrounds": 2,
    "relock_walls_s": [
      34.91
    ],
    "carry_px_err_mean": 9.2,
    "carry_frames": 553,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 4.17,
      "frac_box_closer_distractor": 0.15,
      "n_boxed_twin_frames": 553,
      "final_d_true_m": 27.01,
      "final_d_dist_m": 2.33,
      "closest_at_end": "distractor",
      "relock_on": [
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
