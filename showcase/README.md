# Showcase — what the system does today

Curated demo material for the current end-to-end system. Everything here is a real
run, not a mock-up. Eight examples: four where it works, four where it fails.

**Source:** `experiments/2026-07-20-carry-capacity/runs/T/` — arm T is the shipped
configuration, re-run on 2026-07-20 as the replication control for P5.19. It reproduced
P5.19 cell-for-cell (0 flips), so these clips are the current system, not a variant.

- Video: UAV123 (real aerial footage, 1280x720, 30 fps)
- Model: Qwen2-VL-2B LoRA, GGUF Q8_0 + SAM2.1-hiera-tiny mask carry (zero-shot)
- Matrix: 26 clips x 2 legs (WSEL / SWAP) = 52 cells; arm T scored WSEL 22/26, SWAP 20/26

## How to read the files

Each example has a `.mp4` (the whole run) and a `.png` (the moment of delivery).

| Colour | In the `.png` | In the `.mp4` |
|---|---|---|
| green | the box the system delivered to the operator | the box the system is holding |
| red | ground truth for the target the operator asked for | same |
| blue | ground truth for the decoy object | not drawn |

The `.png` also carries the scores in its top bar: `iou_t` = overlap with the target,
`iou_d` = overlap with the decoy. A cell passes at IoU >= 0.5 against whichever object
the operator asked for.

**For the failures, look at the `.png` first.** It labels target vs decoy and shows the
numbers; the clip only shows how it got there, and a drifted box can be a few pixels
wide on screen.

In every clip the first third reads `no box yet`. That is the point of the design: the
system is watching and tracking candidates before any order arrives. The order lands
mid-clip and the box is delivered in ~0.0 s, because the object was already being held.

## works/

**01 — locks the red car instantly** (`car18`, IoU 0.92, mask coverage 1.00)
Sports car on an open desert road, with a parked SUV and pedestrians as the decoy.
Order arrives at frame 390, box delivered immediately and stays welded to the car.
The cleanest single example in the matrix.

**02 — picks the white van, not the silver car** (`car10`, IoU 0.97 against the decoy)
Two vehicles on the same palm-lined road. Here the operator asks for the *other* one
(the SWAP leg), and the system delivers the van rather than defaulting to the object it
had been tracking. This is the discrimination test, and the highest overlap score of the
whole matrix.

**03 — follows the man in the hat among pedestrians** (`person20`, IoU 0.90, coverage 1.00)
Not a vehicle. Busy plaza, a couple walking as the decoy, target partly shaded and
close to camera. Shows the approach is not car-specific.

**04 — holds a white car through 16 s of silence** (`car9`, IoU 0.91, coverage 0.97)
Long idle window with no order, target crossing under an overhead gantry. The lock
survives the occlusion and the wait.

## fails/

**01 — lock lost, nothing delivered at all** (`car7`)
The honest failure mode: the carry died during the idle window, so when the order came
there was no box to hand over. The system delivers nothing rather than a wrong box.
No clip exists for this cell because there was no track to render.

**02 — lock drifts to a distant car** (`car9`, IoU 0.00)
The green box has walked up the road to a vehicle near the horizon while the real target
(red) is mid-frame. A confident box on the wrong object — worse than delivering nothing,
because the operator has no signal that it is wrong.

**03 — lock slides onto empty water** (`wakeboard3`, IoU 0.00)
Wakeboarder behind a boat. The mask leaves both objects entirely and ends up on open
water at the right image edge. Low-texture background, small fast target.

**04 — delivers the wrong car of two** (`car9`, IoU 0.32 target / 0.00 decoy)
The operator asked for the dark car (blue), the system handed over the white one (red).
Not a tracking failure: the carry was healthy, the wrong object was chosen.

## Caveats, stated plainly

- **Failures are concentrated in one place.** 8 of the 10 residual failures in this matrix
  are carry drift on the `car*` clips, mostly the two above. Swapping in a larger tracker
  (SAM2 hiera-small, P5.20) recovered zero of them and regressed one, so this is a real
  open limitation, not a budget problem.
- **Four cells are excluded from this folder.** Three cells in this run show a delivered
  box drawn in a different place from the box that was scored, and all three are "grace
  delivery" cells (P5.19). Until that is resolved they are not shown here, and the
  showcase picks avoid them.
- **These are offline replays on recorded video**, at the shipped model and settings, not
  a live flight. The flight loop is Part IV; this folder is the perception/select stack.

## Reproducing

The clips are copies, renamed. Originals and their `results.json` are at
`experiments/2026-07-20-carry-capacity/runs/T/<cell>/`, where `<cell>` is
`DSC_{WSEL,SWAP}_<clip>_<prompt frame>` — e.g. `works/01` is `DSC_WSEL_car18_150`.

The `.mp4` files total ~203 MB and are gitignored; the `.png` stills (~11 MB) are tracked,
so this README stays readable from a clone without the video.
