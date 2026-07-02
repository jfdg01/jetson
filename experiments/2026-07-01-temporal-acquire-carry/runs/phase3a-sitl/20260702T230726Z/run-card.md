# Run `20260702T230726Z` — phase3a-sitl-integrated

- **Created (UTC):** 2026-07-02T23:07:26.883476+00:00
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
  "speed": 1.0,
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
    "speed_ms": 1.0,
    "image_size": 1024,
    "n_frames": 1461,
    "achieved_hz": 19.5,
    "carry_fps": 20.5,
    "in_fov_frac": 1.0,
    "first_lock_s": 4.66,
    "n_acquire_attempts": 5,
    "n_rejected_acquires": 3,
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
        4.66,
        [
          256.0,
          33.6,
          396.8,
          288.0
        ],
        true
      ],
      [
        35.22,
        [
          153.6,
          374.4,
          448.0,
          480.0
        ],
        false
      ],
      [
        37.42,
        [
          44.8,
          4.8,
          64.0,
          19.2
        ],
        false
      ],
      [
        39.73,
        [
          294.4,
          0.0,
          428.8,
          144.0
        ],
        true
      ]
    ],
    "n_regrounds": 1,
    "relock_walls_s": [
      6.91
    ],
    "carry_px_err_mean": 49.9,
    "carry_frames": 1170,
    "recovered_after_occlusion": true
  },
  "gate_speed_ms": 1.0,
  "gate": "PASS"
}
```

## Notes

_(anomalies, warm-up, variance — fill in)_
