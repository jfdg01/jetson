# Run `20260703T175250Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T17:52:50.604793+00:00
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
    "n_frames": 2951,
    "duration_s": 150.0,
    "achieved_hz": 19.7,
    "carry_fps": 20.6,
    "in_fov_frac": 1.0,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 23,
    "n_rejected_acquires": 8,
    "n_reground_gate_rejects": 13,
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
        34.89,
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
        37.25,
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
        39.5,
        [
          281.6,
          0.0,
          409.6,
          28.8
        ],
        false,
        "size"
      ],
      [
        41.8,
        [
          288.0,
          0.0,
          403.2,
          72.0
        ],
        false,
        "size"
      ],
      [
        44.11,
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
        46.41,
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
        48.71,
        [
          198.4,
          0.0,
          409.6,
          168.0
        ],
        false,
        "gate"
      ],
      [
        51.12,
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
        53.42,
        [
          192.0,
          0.0,
          480.0,
          230.4
        ],
        false,
        "size"
      ],
      [
        55.72,
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
        58.03,
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
        60.33,
        [
          262.4,
          0.0,
          409.6,
          321.6
        ],
        false,
        "gate"
      ],
      [
        62.63,
        [
          262.4,
          0.0,
          416.0,
          345.6
        ],
        false,
        "gate"
      ],
      [
        64.94,
        [
          256.0,
          0.0,
          416.0,
          379.2
        ],
        false,
        "gate"
      ],
      [
        67.24,
        [
          249.6,
          0.0,
          416.0,
          417.6
        ],
        false,
        "gate"
      ],
      [
        69.54,
        [
          249.6,
          0.0,
          416.0,
          446.4
        ],
        false,
        "gate"
      ],
      [
        71.95,
        [
          249.6,
          240.0,
          390.4,
          480.0
        ],
        false,
        "gate"
      ],
      [
        74.35,
        [
          243.2,
          278.4,
          384.0,
          480.0
        ],
        false,
        "gate"
      ],
      [
        76.75,
        [
          243.2,
          307.2,
          377.6,
          480.0
        ],
        false,
        "gate"
      ],
      [
        79.16,
        [
          243.2,
          340.8,
          377.6,
          480.0
        ],
        false,
        "gate"
      ],
      [
        81.46,
        [
          281.6,
          0.0,
          422.4,
          220.8
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      49.02
    ],
    "carry_px_err_mean": 13.5,
    "carry_frames": 1819,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 1819,
      "final_d_true_m": 0.21,
      "final_d_dist_m": 24.53,
      "final_d_dist2_m": null,
      "closest_at_end": "true",
      "relock_on": [
        "true"
      ]
    }
  },
  "gate_speed_ms": 0.25,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
