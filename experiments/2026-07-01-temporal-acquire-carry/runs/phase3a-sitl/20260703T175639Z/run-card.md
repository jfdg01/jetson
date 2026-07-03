# Run `20260703T175639Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T17:56:39.261186+00:00
- **git SHA:** `5be880ccfc2073ad8ccb8563c6c5f3a493084b5a`  ⚠️ DIRTY TREE
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
    "n_frames": 2977,
    "duration_s": 150.0,
    "achieved_hz": 19.8,
    "carry_fps": 20.6,
    "in_fov_frac": 0.3712,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 53,
    "n_rejected_acquires": 40,
    "n_reground_gate_rejects": 11,
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
        34.81,
        [
          352.0,
          283.2,
          371.2,
          393.6
        ],
        false,
        "size"
      ],
      [
        37.21,
        [
          243.2,
          312.0,
          544.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        39.51,
        [
          377.6,
          0.0,
          524.8,
          62.4
        ],
        false,
        "size"
      ],
      [
        41.87,
        [
          352.0,
          0.0,
          640.0,
          110.4
        ],
        false,
        "size"
      ],
      [
        44.17,
        [
          377.6,
          0.0,
          441.6,
          120.0
        ],
        false,
        "gate"
      ],
      [
        46.52,
        [
          403.2,
          0.0,
          640.0,
          172.8
        ],
        false,
        "size"
      ],
      [
        48.88,
        [
          499.2,
          0.0,
          640.0,
          216.0
        ],
        false,
        "gate"
      ],
      [
        51.23,
        [
          544.0,
          9.6,
          640.0,
          254.4
        ],
        false,
        "gate"
      ],
      [
        53.58,
        [
          569.6,
          43.2,
          640.0,
          288.0
        ],
        false,
        "gate"
      ],
      [
        55.99,
        [
          601.6,
          48.0,
          640.0,
          326.4
        ],
        false,
        "size"
      ],
      [
        58.34,
        [
          6.4,
          273.6,
          633.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        60.69,
        [
          64.0,
          139.2,
          307.2,
          350.4
        ],
        false,
        "size"
      ],
      [
        63.05,
        [
          185.6,
          96.0,
          275.2,
          177.6
        ],
        false,
        "size"
      ],
      [
        65.4,
        [
          217.6,
          134.4,
          300.8,
          216.0
        ],
        false,
        "size"
      ],
      [
        67.7,
        [
          134.4,
          0.0,
          428.8,
          115.2
        ],
        false,
        "size"
      ],
      [
        70.01,
        [
          153.6,
          0.0,
          454.4,
          158.4
        ],
        false,
        "size"
      ],
      [
        72.31,
        [
          524.8,
          9.6,
          582.4,
          52.8
        ],
        false,
        "size"
      ],
      [
        74.56,
        [
          96.0,
          0.0,
          140.8,
          43.2
        ],
        false,
        "size"
      ],
      [
        76.87,
        [
          128.0,
          33.6,
          172.8,
          81.6
        ],
        false,
        "size"
      ],
      [
        79.22,
        [
          249.6,
          124.8,
          550.4,
          312.0
        ],
        false,
        "size"
      ],
      [
        81.57,
        [
          268.8,
          182.4,
          409.6,
          345.6
        ],
        false,
        "gate"
      ],
      [
        83.93,
        [
          294.4,
          196.8,
          601.6,
          384.0
        ],
        false,
        "size"
      ],
      [
        86.29,
        [
          211.2,
          192.0,
          268.8,
          244.8
        ],
        false,
        "size"
      ],
      [
        88.64,
        [
          236.8,
          230.4,
          294.4,
          283.2
        ],
        false,
        "size"
      ],
      [
        90.99,
        [
          268.8,
          268.8,
          313.6,
          326.4
        ],
        false,
        "size"
      ],
      [
        93.25,
        [
          38.4,
          4.8,
          96.0,
          76.8
        ],
        false,
        "size"
      ],
      [
        95.55,
        [
          51.2,
          52.8,
          108.8,
          120.0
        ],
        false,
        "size"
      ],
      [
        97.75,
        [
          51.2,
          0.0,
          83.2,
          38.4
        ],
        false,
        "size"
      ],
      [
        100.06,
        [
          70.4,
          33.6,
          115.2,
          76.8
        ],
        false,
        "size"
      ],
      [
        102.41,
        [
          128.0,
          163.2,
          192.0,
          230.4
        ],
        false,
        "size"
      ],
      [
        104.76,
        [
          128.0,
          110.4,
          217.6,
          273.6
        ],
        false,
        "gate"
      ],
      [
        107.12,
        [
          147.2,
          158.4,
          192.0,
          201.6
        ],
        false,
        "size"
      ],
      [
        109.48,
        [
          179.2,
          196.8,
          230.4,
          240.0
        ],
        false,
        "size"
      ],
      [
        111.83,
        [
          198.4,
          235.2,
          249.6,
          292.8
        ],
        false,
        "size"
      ],
      [
        114.18,
        [
          217.6,
          273.6,
          268.8,
          326.4
        ],
        false,
        "size"
      ],
      [
        116.54,
        [
          256.0,
          307.2,
          294.4,
          355.2
        ],
        false,
        "size"
      ],
      [
        118.89,
        [
          268.8,
          345.6,
          320.0,
          398.4
        ],
        false,
        "size"
      ],
      [
        121.24,
        [
          288.0,
          379.2,
          345.6,
          436.8
        ],
        false,
        "size"
      ],
      [
        123.6,
        [
          428.8,
          345.6,
          454.4,
          364.8
        ],
        false,
        "size"
      ],
      [
        125.95,
        [
          441.6,
          379.2,
          473.6,
          403.2
        ],
        false,
        "size"
      ],
      [
        128.3,
        [
          294.4,
          153.6,
          460.8,
          292.8
        ],
        false,
        "gate"
      ],
      [
        130.71,
        [
          326.4,
          355.2,
          416.0,
          480.0
        ],
        false,
        "gate"
      ],
      [
        133.12,
        [
          364.8,
          398.4,
          435.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        135.52,
        [
          390.4,
          436.8,
          448.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        137.92,
        [
          217.6,
          28.8,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        140.23,
        [
          256.0,
          0.0,
          320.0,
          48.0
        ],
        false,
        "size"
      ],
      [
        142.58,
        [
          300.8,
          105.6,
          480.0,
          340.8
        ],
        false,
        "gate"
      ],
      [
        144.93,
        [
          332.8,
          148.8,
          505.6,
          379.2
        ],
        false,
        "gate"
      ],
      [
        147.29,
        [
          352.0,
          192.0,
          537.6,
          412.8
        ],
        false,
        "gate"
      ],
      [
        149.59,
        [
          32.0,
          4.8,
          403.2,
          480.0
        ],
        false,
        "size"
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [],
    "carry_px_err_mean": 8.7,
    "carry_frames": 475,
    "recovered_after_occlusion": false,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 475,
      "final_d_true_m": 26.85,
      "final_d_dist_m": 35.84,
      "final_d_dist2_m": null,
      "closest_at_end": "true",
      "relock_on": []
    }
  },
  "gate_speed_ms": 0.25,
  "gate": "FAIL"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
