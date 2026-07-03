# Run `20260703T170022Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T17:00:22.156915+00:00
- **git SHA:** `59c1d1a3bd2af0c5791695b7cd9708e4c547602c`  ⚠️ DIRTY TREE
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
  "decoy2_m": 7.0,
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
    "n_frames": 2961,
    "duration_s": 150.0,
    "achieved_hz": 19.7,
    "carry_fps": 20.4,
    "in_fov_frac": 0.6295,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 46,
    "n_rejected_acquires": 29,
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
          256.0,
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
          320.0,
          422.4
        ],
        false,
        "size"
      ],
      [
        39.51,
        [
          147.2,
          321.6,
          460.8,
          480.0
        ],
        false,
        "size"
      ],
      [
        41.82,
        [
          300.8,
          0.0,
          409.6,
          67.2
        ],
        false,
        "size"
      ],
      [
        44.12,
        [
          211.2,
          0.0,
          320.0,
          100.8
        ],
        false,
        "size"
      ],
      [
        46.42,
        [
          204.8,
          0.0,
          499.2,
          120.0
        ],
        false,
        "size"
      ],
      [
        48.73,
        [
          288.0,
          0.0,
          409.6,
          163.2
        ],
        false,
        "gate"
      ],
      [
        51.13,
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
        53.53,
        [
          0.0,
          182.4,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        55.84,
        [
          288.0,
          0.0,
          428.8,
          264.0
        ],
        false,
        "gate"
      ],
      [
        58.14,
        [
          281.6,
          0.0,
          428.8,
          302.4
        ],
        false,
        "gate"
      ],
      [
        60.44,
        [
          281.6,
          0.0,
          428.8,
          336.0
        ],
        false,
        "gate"
      ],
      [
        62.75,
        [
          275.2,
          0.0,
          435.2,
          360.0
        ],
        false,
        "gate"
      ],
      [
        65.05,
        [
          268.8,
          0.0,
          435.2,
          393.6
        ],
        false,
        "gate"
      ],
      [
        67.35,
        [
          198.4,
          0.0,
          512.0,
          436.8
        ],
        false,
        "size"
      ],
      [
        69.65,
        [
          294.4,
          0.0,
          422.4,
          235.2
        ],
        true,
        ""
      ],
      [
        87.99,
        [
          211.2,
          412.8,
          332.8,
          480.0
        ],
        false,
        "size"
      ],
      [
        90.4,
        [
          217.6,
          388.8,
          339.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        92.8,
        [
          217.6,
          388.8,
          339.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        95.2,
        [
          217.6,
          388.8,
          339.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        97.61,
        [
          217.6,
          384.0,
          339.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        100.01,
        [
          217.6,
          384.0,
          339.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        102.41,
        [
          217.6,
          388.8,
          339.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        104.82,
        [
          224.0,
          388.8,
          339.2,
          480.0
        ],
        false,
        "size"
      ],
      [
        107.22,
        [
          224.0,
          384.0,
          345.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        109.62,
        [
          224.0,
          384.0,
          345.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        112.03,
        [
          224.0,
          384.0,
          345.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        114.43,
        [
          224.0,
          384.0,
          345.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        116.83,
        [
          224.0,
          379.2,
          345.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        119.24,
        [
          224.0,
          379.2,
          352.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        121.64,
        [
          224.0,
          379.2,
          345.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        123.94,
        [
          262.4,
          0.0,
          390.4,
          230.4
        ],
        false,
        "gate"
      ],
      [
        126.25,
        [
          262.4,
          0.0,
          403.2,
          230.4
        ],
        false,
        "gate"
      ],
      [
        128.56,
        [
          262.4,
          0.0,
          384.0,
          230.4
        ],
        false,
        "gate"
      ],
      [
        130.86,
        [
          262.4,
          0.0,
          384.0,
          230.4
        ],
        false,
        "gate"
      ],
      [
        133.26,
        [
          230.4,
          379.2,
          352.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        135.67,
        [
          230.4,
          379.2,
          358.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        138.07,
        [
          230.4,
          379.2,
          358.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        140.47,
        [
          236.8,
          379.2,
          358.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        142.78,
        [
          268.8,
          0.0,
          390.4,
          225.6
        ],
        false,
        "gate"
      ],
      [
        145.08,
        [
          268.8,
          0.0,
          390.4,
          225.6
        ],
        false,
        "gate"
      ],
      [
        147.38,
        [
          268.8,
          0.0,
          390.4,
          225.6
        ],
        false,
        "gate"
      ],
      [
        149.69,
        [
          268.8,
          0.0,
          396.8,
          225.6
        ],
        false,
        "gate"
      ]
    ],
    "n_regrounds": 2,
    "relock_walls_s": [
      37.31
    ],
    "carry_px_err_mean": 18.2,
    "carry_frames": 717,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 717,
      "final_d_true_m": 20.18,
      "final_d_dist_m": 4.57,
      "final_d_dist2_m": 2.44,
      "closest_at_end": "distractor2",
      "relock_on": [
        "true"
      ]
    }
  },
  "gate_speed_ms": 0.25,
  "gate": "FAIL"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
