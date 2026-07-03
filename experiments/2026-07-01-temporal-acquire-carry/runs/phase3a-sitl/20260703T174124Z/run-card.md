# Run `20260703T174124Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T17:41:24.580915+00:00
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
    "n_frames": 2971,
    "duration_s": 150.0,
    "achieved_hz": 19.8,
    "carry_fps": 20.8,
    "in_fov_frac": 0.6796,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 44,
    "n_rejected_acquires": 33,
    "n_reground_gate_rejects": 8,
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
        34.78,
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
        37.14,
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
        39.39,
        [
          288.0,
          0.0,
          409.6,
          28.8
        ],
        false,
        "size"
      ],
      [
        41.69,
        [
          288.0,
          0.0,
          409.6,
          67.2
        ],
        false,
        "size"
      ],
      [
        44.0,
        [
          204.8,
          0.0,
          409.6,
          96.0
        ],
        false,
        "size"
      ],
      [
        46.3,
        [
          204.8,
          0.0,
          416.0,
          124.8
        ],
        false,
        "gate"
      ],
      [
        48.6,
        [
          204.8,
          0.0,
          492.8,
          163.2
        ],
        false,
        "size"
      ],
      [
        51.0,
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
        53.41,
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
        55.71,
        [
          268.8,
          14.4,
          403.2,
          264.0
        ],
        false,
        "gate"
      ],
      [
        58.01,
        [
          262.4,
          0.0,
          390.4,
          292.8
        ],
        false,
        "gate"
      ],
      [
        60.32,
        [
          262.4,
          0.0,
          409.6,
          326.4
        ],
        false,
        "gate"
      ],
      [
        62.62,
        [
          256.0,
          0.0,
          403.2,
          350.4
        ],
        false,
        "gate"
      ],
      [
        64.92,
        [
          256.0,
          0.0,
          416.0,
          388.8
        ],
        false,
        "gate"
      ],
      [
        67.23,
        [
          256.0,
          0.0,
          416.0,
          417.6
        ],
        false,
        "gate"
      ],
      [
        69.58,
        [
          249.6,
          216.0,
          390.4,
          451.2
        ],
        false,
        "gate"
      ],
      [
        71.88,
        [
          281.6,
          0.0,
          416.0,
          225.6
        ],
        true,
        ""
      ],
      [
        95.22,
        [
          262.4,
          384.0,
          281.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        97.52,
        [
          249.6,
          0.0,
          371.2,
          115.2
        ],
        false,
        "size"
      ],
      [
        99.82,
        [
          249.6,
          0.0,
          364.8,
          76.8
        ],
        false,
        "size"
      ],
      [
        102.08,
        [
          256.0,
          0.0,
          364.8,
          38.4
        ],
        false,
        "size"
      ],
      [
        104.43,
        [
          243.2,
          340.8,
          262.4,
          470.4
        ],
        false,
        "size"
      ],
      [
        106.78,
        [
          243.2,
          350.4,
          256.0,
          470.4
        ],
        false,
        "size"
      ],
      [
        109.14,
        [
          243.2,
          340.8,
          262.4,
          470.4
        ],
        false,
        "size"
      ],
      [
        111.49,
        [
          236.8,
          115.2,
          281.6,
          240.0
        ],
        false,
        "size"
      ],
      [
        113.84,
        [
          230.4,
          345.6,
          249.6,
          460.8
        ],
        false,
        "size"
      ],
      [
        116.2,
        [
          224.0,
          340.8,
          243.2,
          465.6
        ],
        false,
        "size"
      ],
      [
        118.55,
        [
          243.2,
          115.2,
          268.8,
          240.0
        ],
        false,
        "size"
      ],
      [
        120.9,
        [
          236.8,
          110.4,
          268.8,
          240.0
        ],
        false,
        "size"
      ],
      [
        123.26,
        [
          217.6,
          345.6,
          230.4,
          460.8
        ],
        false,
        "size"
      ],
      [
        125.61,
        [
          230.4,
          110.4,
          249.6,
          235.2
        ],
        false,
        "size"
      ],
      [
        127.96,
        [
          230.4,
          110.4,
          249.6,
          235.2
        ],
        false,
        "size"
      ],
      [
        130.32,
        [
          224.0,
          110.4,
          243.2,
          235.2
        ],
        false,
        "size"
      ],
      [
        132.67,
        [
          217.6,
          110.4,
          236.8,
          235.2
        ],
        false,
        "size"
      ],
      [
        135.02,
        [
          179.2,
          340.8,
          198.4,
          460.8
        ],
        false,
        "size"
      ],
      [
        137.38,
        [
          179.2,
          105.6,
          230.4,
          240.0
        ],
        false,
        "size"
      ],
      [
        139.73,
        [
          172.8,
          340.8,
          192.0,
          465.6
        ],
        false,
        "size"
      ],
      [
        142.08,
        [
          172.8,
          331.2,
          192.0,
          460.8
        ],
        false,
        "size"
      ],
      [
        144.44,
        [
          153.6,
          336.0,
          172.8,
          460.8
        ],
        false,
        "size"
      ],
      [
        146.79,
        [
          153.6,
          336.0,
          179.2,
          456.0
        ],
        false,
        "size"
      ],
      [
        149.14,
        [
          160.0,
          105.6,
          211.2,
          230.4
        ],
        false,
        "size"
      ]
    ],
    "n_regrounds": 2,
    "relock_walls_s": [
      39.45
    ],
    "carry_px_err_mean": 14.1,
    "carry_frames": 826,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 826,
      "final_d_true_m": 18.15,
      "final_d_dist_m": 7.18,
      "final_d_dist2_m": null,
      "closest_at_end": "distractor",
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
