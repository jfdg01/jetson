# Run `20260703T174901Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T17:49:01.945868+00:00
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
    "n_frames": 2937,
    "duration_s": 150.0,
    "achieved_hz": 19.6,
    "carry_fps": 20.4,
    "in_fov_frac": 1.0,
    "first_lock_s": 4.71,
    "n_acquire_attempts": 24,
    "n_rejected_acquires": 9,
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
        34.87,
        [
          294.4,
          273.6,
          313.6,
          388.8
        ],
        false,
        "size"
      ],
      [
        37.23,
        [
          294.4,
          307.2,
          320.0,
          417.6
        ],
        false,
        "size"
      ],
      [
        39.48,
        [
          281.6,
          0.0,
          416.0,
          28.8
        ],
        false,
        "size"
      ],
      [
        41.78,
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
        44.09,
        [
          288.0,
          0.0,
          409.6,
          100.8
        ],
        false,
        "size"
      ],
      [
        46.39,
        [
          204.8,
          0.0,
          422.4,
          124.8
        ],
        false,
        "gate"
      ],
      [
        48.69,
        [
          294.4,
          0.0,
          409.6,
          158.4
        ],
        false,
        "gate"
      ],
      [
        51.05,
        [
          0.0,
          225.6,
          633.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        53.45,
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
        55.75,
        [
          288.0,
          0.0,
          409.6,
          264.0
        ],
        false,
        "gate"
      ],
      [
        58.06,
        [
          275.2,
          0.0,
          416.0,
          292.8
        ],
        false,
        "gate"
      ],
      [
        60.36,
        [
          275.2,
          0.0,
          422.4,
          326.4
        ],
        false,
        "gate"
      ],
      [
        62.66,
        [
          268.8,
          0.0,
          422.4,
          350.4
        ],
        false,
        "gate"
      ],
      [
        64.97,
        [
          268.8,
          0.0,
          422.4,
          384.0
        ],
        false,
        "gate"
      ],
      [
        67.27,
        [
          268.8,
          0.0,
          428.8,
          417.6
        ],
        false,
        "gate"
      ],
      [
        69.62,
        [
          268.8,
          211.2,
          403.2,
          446.4
        ],
        false,
        "gate"
      ],
      [
        72.03,
        [
          262.4,
          244.8,
          409.6,
          480.0
        ],
        false,
        "gate"
      ],
      [
        74.43,
        [
          262.4,
          278.4,
          409.6,
          480.0
        ],
        false,
        "gate"
      ],
      [
        76.83,
        [
          268.8,
          307.2,
          396.8,
          480.0
        ],
        false,
        "gate"
      ],
      [
        79.24,
        [
          268.8,
          340.8,
          396.8,
          480.0
        ],
        false,
        "gate"
      ],
      [
        81.64,
        [
          275.2,
          374.4,
          396.8,
          480.0
        ],
        false,
        "size"
      ],
      [
        83.94,
        [
          307.2,
          0.0,
          435.2,
          220.8
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      51.55
    ],
    "carry_px_err_mean": 13.5,
    "carry_frames": 1755,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 1755,
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
