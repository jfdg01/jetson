# Run `20260703T103616Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-03T10:36:16.790147+00:00
- **git SHA:** `4ea020fad64407df51970bcbaeb21bb6d58176cd`  ⚠️ DIRTY TREE
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
  "speed": 1.5,
  "duration_s": 75.0,
  "hz": 20,
  "image_size": 1024,
  "sam2": "facebook/sam2.1-hiera-tiny",
  "validate": "sizeprior-0.5-2.0",
  "deadreckon": true,
  "twin": null,
  "retarget_t": null,
  "loss_gate": "motion",
  "score_tau": 0.0,
  "dr": "pursuit",
  "acquire_hold": "motion",
  "reground_gate": "none",
  "vmax": 4.0,
  "catchup_replay": true,
  "carry": "host-3090"
}
```

## Results

```json
{
  "trial": {
    "speed_ms": 1.5,
    "image_size": 1024,
    "n_frames": 1467,
    "duration_s": 75.0,
    "achieved_hz": 19.6,
    "carry_fps": 20.4,
    "in_fov_frac": 1.0,
    "first_lock_s": 16.57,
    "n_acquire_attempts": 18,
    "n_rejected_acquires": 16,
    "n_reground_gate_rejects": 0,
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
          294.4,
          230.4,
          320.0,
          350.4
        ],
        false,
        "size"
      ],
      [
        7.11,
        [
          294.4,
          422.4,
          313.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        9.52,
        [
          294.4,
          388.8,
          320.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        11.92,
        [
          294.4,
          369.6,
          313.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        14.27,
        [
          294.4,
          340.8,
          313.6,
          470.4
        ],
        false,
        "size"
      ],
      [
        16.57,
        [
          268.8,
          0.0,
          396.8,
          216.0
        ],
        true,
        ""
      ],
      [
        35.15,
        [
          0.0,
          0.0,
          64.0,
          48.0
        ],
        false,
        "size"
      ],
      [
        37.4,
        [
          403.2,
          0.0,
          492.8,
          19.2
        ],
        false,
        "size"
      ],
      [
        39.81,
        [
          0.0,
          168.0,
          640.0,
          480.0
        ],
        false,
        "size"
      ],
      [
        42.16,
        [
          345.6,
          244.8,
          364.8,
          364.8
        ],
        false,
        "size"
      ],
      [
        44.56,
        [
          352.0,
          446.4,
          364.8,
          480.0
        ],
        false,
        "size"
      ],
      [
        46.97,
        [
          364.8,
          417.6,
          377.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        49.37,
        [
          371.2,
          393.6,
          390.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        51.77,
        [
          377.6,
          369.6,
          409.6,
          480.0
        ],
        false,
        "size"
      ],
      [
        54.13,
        [
          396.8,
          345.6,
          422.4,
          470.4
        ],
        false,
        "size"
      ],
      [
        56.48,
        [
          268.8,
          0.0,
          614.4,
          480.0
        ],
        false,
        "size"
      ],
      [
        58.78,
        [
          396.8,
          0.0,
          537.6,
          235.2
        ],
        true,
        ""
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      25.89
    ],
    "carry_px_err_mean": 80.2,
    "carry_frames": 558,
    "recovered_after_occlusion": true
  },
  "gate_speed_ms": 1.5,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
