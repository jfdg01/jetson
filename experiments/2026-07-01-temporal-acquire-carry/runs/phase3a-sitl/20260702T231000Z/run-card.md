# Run `20260702T231000Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-02T23:10:00.597122+00:00
- **git SHA:** `20c7c3b0555f5bd481542aa0f555b71f984ae9b3`  ⚠️ DIRTY TREE
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
  "loss_gate": "motion",
  "score_tau": 0.0,
  "dr": "pursuit",
  "acquire_hold": "motion",
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
    "n_frames": 1448,
    "achieved_hz": 19.3,
    "carry_fps": 20.1,
    "in_fov_frac": 1.0,
    "first_lock_s": 16.57,
    "n_acquire_attempts": 10,
    "n_rejected_acquires": 8,
    "acquire_log": [
      [
        2.35,
        [
          288.0,
          355.2,
          307.2,
          480.0
        ],
        false
      ],
      [
        4.71,
        [
          294.4,
          230.4,
          320.0,
          350.4
        ],
        false
      ],
      [
        7.11,
        [
          294.4,
          422.4,
          313.6,
          480.0
        ],
        false
      ],
      [
        9.51,
        [
          294.4,
          388.8,
          320.0,
          480.0
        ],
        false
      ],
      [
        11.92,
        [
          294.4,
          369.6,
          313.6,
          480.0
        ],
        false
      ],
      [
        14.27,
        [
          294.4,
          340.8,
          313.6,
          470.4
        ],
        false
      ],
      [
        16.57,
        [
          268.8,
          0.0,
          396.8,
          216.0
        ],
        true
      ],
      [
        35.43,
        [
          0.0,
          436.8,
          192.0,
          480.0
        ],
        false
      ],
      [
        37.68,
        [
          294.4,
          0.0,
          422.4,
          38.4
        ],
        false
      ],
      [
        39.98,
        [
          300.8,
          0.0,
          441.6,
          240.0
        ],
        true
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      7.05
    ],
    "carry_px_err_mean": 75.7,
    "carry_frames": 919,
    "recovered_after_occlusion": true
  },
  "gate_speed_ms": 1.5,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
