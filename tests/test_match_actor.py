"""match_actor must lock on a tight box that misses the vehicle's mesh origin.

The regression this pins: a SAM2 box clipped to a truck's cargo body excludes the
truck's origin point, and the old point-in-box test therefore called a
pixel-perfect lock a permanent drift (UI showed "DRIFT 53s off target").

Signatures take a cached (actor, bounding_box) list and one world snapshot, so the
match makes zero per-actor RPCs -- reading v.bounding_box per vehicle per step cost
~540 ms and froze the display (fix 5bdeff1). The fakes below mirror that shape.
"""
import importlib.util
import sys
from pathlib import Path

import carla

spec = importlib.util.spec_from_file_location(
    "carla_debug_ui", Path(__file__).resolve().parents[1] / "runners" / "carla_debug_ui.py")
ui = importlib.util.module_from_spec(spec)
sys.modules["carla_debug_ui"] = ui
spec.loader.exec_module(ui)


class FakeActor:
    def __init__(self, aid, loc, extent):
        self.id = aid
        self.type_id = "vehicle.fake.fake"
        self._tf = carla.Transform(loc)
        self.bounding_box = carla.BoundingBox(carla.Location(0, 0, 0), extent)

    def get_transform(self):
        return self._tf

    def get_location(self):
        return self._tf.location


class FakeSnap:
    """A world snapshot: snap.find(id) -> something with .get_transform()."""

    def __init__(self, actors):
        self._a = {a.id: a for a in actors}

    def find(self, aid):
        return self._a.get(aid)


def veh(actors):
    """What veh_list() hands match_actor: (actor, cached bounding_box) pairs."""
    return [(a, a.bounding_box) for a in actors]


def box_of(a, cam_tf):
    return ui.actor_box(a.bounding_box, cam_tf, a.get_transform())


# camera 60 m up, nose down, looking at the world origin
CAM = carla.Transform(carla.Location(0, 0, 60), carla.Rotation(pitch=-90))


def test_tight_box_missing_origin_still_matches():
    # a 8x2.5x3.5 m truck at the origin -- long axis along world x
    truck = FakeActor(7, carla.Location(0, 0, 1.75), carla.Vector3D(4.0, 1.25, 1.75))
    full = box_of(truck, CAM)
    # crop to the rear 40% of the truck: the projected origin is now OUTSIDE
    w = full[2] - full[0]
    tight = (full[0], full[1], full[0] + 0.4 * w, full[3])
    cx = (tight[0] + tight[2]) / 2.0
    assert not (tight[0] <= (full[0] + full[2]) / 2.0 <= tight[2]), "origin must be out"
    assert ui.match_actor(CAM, tight, veh([truck]), FakeSnap([truck])) is truck
    assert cx < (full[0] + full[2]) / 2.0


def test_box_on_empty_asphalt_is_a_drift():
    truck = FakeActor(7, carla.Location(0, 0, 1.75), carla.Vector3D(4.0, 1.25, 1.75))
    far = ui.project(carla.Location(40, 40, 0), CAM)
    empty = (far[0] - 20, far[1] - 20, far[0] + 20, far[1] + 20)
    assert ui.match_actor(CAM, empty, veh([truck]), FakeSnap([truck])) is None


def test_nearest_neighbour_does_not_steal_the_lock():
    a = FakeActor(1, carla.Location(0, 0, 0.75), carla.Vector3D(2.2, 0.9, 0.75))
    b = FakeActor(2, carla.Location(8, 0, 0.75), carla.Vector3D(2.2, 0.9, 0.75))
    both, snap = veh([a, b]), FakeSnap([a, b])
    assert ui.match_actor(CAM, box_of(a, CAM), both, snap) is a
    assert ui.match_actor(CAM, box_of(b, CAM), both, snap) is b


def test_actor_that_vanished_since_the_list_was_cached_is_skipped():
    """veh_list refreshes every 2 s, so the snapshot can be missing an actor."""
    a = FakeActor(1, carla.Location(0, 0, 0.75), carla.Vector3D(2.2, 0.9, 0.75))
    gone = FakeActor(2, carla.Location(0, 0, 0.75), carla.Vector3D(2.2, 0.9, 0.75))
    assert ui.match_actor(CAM, box_of(a, CAM), veh([gone, a]), FakeSnap([a])) is a
