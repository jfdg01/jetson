# Run `20260703T180027Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T18:00:27.996556+00:00
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
    "n_acquire_attempts": 23,
    "n_rejected_acquires": 9,
    "n_reground_gate_rejects": 12,
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
          294.4,
          307.2,
          313.6,
          417.6
        ],
        false,
        "size"
      ],
      [
        39.42,
        [
          211.2,
          0.0,
          409.6,
          28.8
        ],
        false,
        "size"
      ],
      [
        41.72,
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
        44.03,
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
        46.33,
        [
          198.4,
          0.0,
          230.4,
          100.8
        ],
        false,
        "size"
      ],
      [
        48.63,
        [
          204.8,
          0.0,
          486.4,
          172.8
        ],
        false,
        "size"
      ],
      [
        51.04,
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
        53.34,
        [
          192.0,
          0.0,
          409.6,
          230.4
        ],
        false,
        "gate"
      ],
      [
        55.65,
        [
          268.8,
          19.2,
          403.2,
          264.0
        ],
        false,
        "gate"
      ],
      [
        57.98,
        [
          262.4,
          0.0,
          390.4,
          288.0
        ],
        false,
        "gate"
      ],
      [
        60.34,
        [
          262.4,
          76.8,
          403.2,
          326.4
        ],
        false,
        "gate"
      ],
      [
        62.64,
        [
          249.6,
          0.0,
          416.0,
          350.4
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
          388.8
        ],
        false,
        "gate"
      ],
      [
        67.25,
        [
          256.0,
          0.0,
          409.6,
          417.6
        ],
        false,
        "gate"
      ],
      [
        69.6,
        [
          256.0,
          216.0,
          390.4,
          451.2
        ],
        false,
        "gate"
      ],
      [
        72.0,
        [
          249.6,
          244.8,
          390.4,
          480.0
        ],
        false,
        "gate"
      ],
      [
        74.41,
        [
          249.6,
          283.2,
          390.4,
          480.0
        ],
        false,
        "gate"
      ],
      [
        76.81,
        [
          249.6,
          312.0,
          377.6,
          480.0
        ],
        false,
        "gate"
      ],
      [
        79.21,
        [
          256.0,
          340.8,
          377.6,
          480.0
        ],
        false,
        "gate"
      ],
      [
        81.52,
        [
          288.0,
          0.0,
          403.2,
          220.8
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      49.06
    ],
    "carry_px_err_mean": 16.7,
    "carry_frames": 1803,
    "recovered_after_occlusion": true,
    "twin": {
      "mode": "decoy",
      "id_switch_s": 0.0,
      "frac_box_closer_distractor": 0.0,
      "n_boxed_twin_frames": 1803,
      "final_d_true_m": 0.12,
      "final_d_dist_m": 24.63,
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
