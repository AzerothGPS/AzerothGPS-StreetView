"""A spot's 26 screenshots -> one 360-degree panorama (equirectangular), for the viewer's
smooth panning.

Every screenshot is a pinhole picture. Its direction is known roughly: the facing the capture
recorded for it (yaw) and the saved camera view it was taken with (pitch: level, up, down,
straight up, straight down). The field of view and each view's real pitch (saved by eye, so
not exactly 45 degrees) are measured first, by making neighboring pictures agree where they
overlap. Then each panorama pixel samples the pictures that see its direction, blended toward
each picture's center. No feature matching.

Panorama: the middle column looks along the spot's first facing (`facing` in the pack); columns
to the right turn right (clockwise); the top row is straight up. Camera axes: x right, y up,
z forward, in a frame where the first facing looks along +z.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

# The saved views by pitch in the image names, and their starting guesses (degrees).
RINGS = {0: "level", 45: "up", -45: "down", 90: "zenith", -90: "nadir"}
GUESS = {"level": 0.0, "up": 45.0, "down": -45.0, "zenith": 88.0, "nadir": -88.0}


@dataclass
class Shot:
    img: np.ndarray  # (h, w, 3) uint8
    yaw: float  # radians counter-clockwise from the spot's first facing (measured)
    ring: str  # "level", "up", "down", "zenith", "nadir"


@dataclass
class Rig:
    hfov: float = 90.0  # horizontal field of view, degrees
    pitch: dict = field(default_factory=lambda: dict(GUESS))  # degrees per ring
    yaw_off: dict = field(default_factory=lambda: {k: 0.0 for k in GUESS})  # degrees per ring (level stays 0)


def axes(yaw: float, pitch: float):
    """Right, up, forward of a camera turned `yaw` radians counter-clockwise and pitched
    `pitch` radians up."""
    lon = -yaw
    f = np.array([math.sin(lon) * math.cos(pitch), math.sin(pitch), math.cos(lon) * math.cos(pitch)])
    r = np.array([math.cos(lon), 0.0, -math.sin(lon)])
    u = np.array([-math.sin(lon) * math.sin(pitch), math.cos(pitch), -math.cos(lon) * math.sin(pitch)])
    return r, u, f


def focal(width: int, hfov_deg: float) -> float:
    return width / 2 / math.tan(math.radians(hfov_deg) / 2)


def camera(shot: Shot, rig: Rig):
    yaw = shot.yaw + math.radians(rig.yaw_off[shot.ring])
    return axes(yaw, math.radians(rig.pitch[shot.ring]))


def project(d: np.ndarray, cam, w: int, h: int, f: float):
    r, u, fw = cam
    x, y, z = d @ r, d @ u, d @ fw
    with np.errstate(divide="ignore", invalid="ignore"):
        px = w / 2 + f * x / z - 0.5
        py = h / 2 - f * y / z - 0.5
    ok = (z > 1e-6) & (px >= 0) & (px <= w - 1) & (py >= 0) & (py <= h - 1)
    return px, py, z, ok


def sample(img: np.ndarray, px: np.ndarray, py: np.ndarray) -> np.ndarray:
    """Bilinear samples (valid coordinates only); img is (h, w) or (h, w, c) float."""
    h, w = img.shape[:2]
    x0 = np.clip(np.floor(px).astype(np.int64), 0, w - 2)
    y0 = np.clip(np.floor(py).astype(np.int64), 0, h - 2)
    fx, fy = px - x0, py - y0
    if img.ndim == 3:
        fx, fy = fx[:, None], fy[:, None]
    a, b = img[y0, x0], img[y0, x0 + 1]
    c, d = img[y0 + 1, x0], img[y0 + 1, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def pixel_dirs(w: int, h: int, f: float, cam, step: int = 1, border: int = 0):
    """Directions of a picture's pixels (every `step`-th), and their (x, y)."""
    ys, xs = np.mgrid[border:h - border:step, border:w - border:step]
    xs, ys = xs.reshape(-1), ys.reshape(-1)
    r, u, fw = cam
    d = (xs + 0.5 - w / 2)[:, None] * r + (h / 2 - (ys + 0.5))[:, None] * u + f * fw
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    return d, xs, ys


def _gray(img: np.ndarray, width: int) -> np.ndarray:
    """Small grayscale copy for measuring (box-averaged to `width` pixels)."""
    h, w = img.shape[:2]
    k = max(1, w // width)
    g = img[: h // k * k, : w // k * k].astype(np.float32).mean(axis=2)
    return g.reshape(h // k, k, w // k, k).mean(axis=(1, 3))


def pairs(shots: list[Shot]) -> list[tuple[int, int]]:
    """Neighboring pictures: along each ring, level to up and down at the same yaw, and the
    straight up/down pictures with every picture of the ring next to them."""
    by = {}
    for i, s in enumerate(shots):
        by.setdefault(s.ring, []).append(i)
    out = []
    for ring in ("level", "up", "down"):
        idx = sorted(by.get(ring, []), key=lambda i: shots[i].yaw % (2 * math.pi))
        out += [(idx[j], idx[(j + 1) % len(idx)]) for j in range(len(idx))] if len(idx) > 1 else []
    for ring in ("up", "down"):
        for i in by.get("level", []):
            j = min(by.get(ring, []), default=None,
                    key=lambda j: abs(math.remainder(shots[j].yaw - shots[i].yaw, 2 * math.pi)))
            if j is not None:
                out.append((i, j))
    for pole, ring in (("zenith", "up"), ("nadir", "down")):
        for p in by.get(pole, []):
            out += [(p, j) for j in by.get(ring, [])]
    return out


def mismatch(shots, grays, rig: Rig, plist, step: int = 3) -> float:
    """Mean gray difference where neighboring pictures overlap (lower is better)."""
    total, count = 0.0, 0
    for a, b in plist:
        ga, gb = grays[a], grays[b]
        h, w = ga.shape
        f = focal(w, rig.hfov)
        d, xs, ys = pixel_dirs(w, h, f, camera(shots[a], rig), step, border=2)
        px, py, _, ok = project(d, camera(shots[b], rig), w, h, f)
        n = int(ok.sum())
        if n < 50:
            total += 60.0 * 50  # (no overlap where there should be some: a bad guess)
            count += 50
            continue
        diff = np.abs(ga[ys[ok], xs[ok]] - sample(gb, px[ok], py[ok]))
        total += float(diff.sum())
        count += n
    return total / max(count, 1)


def _descend(shots, grays, rig: Rig, plist, params, step: float, min_step: float = 0.05) -> float:
    """Coordinate descent: each parameter tries a few offsets (a small line search) in turn,
    until no step of at least min_step helps."""
    def get(p):
        return rig.hfov if p[0] == "hfov" else getattr(rig, p[0])[p[1]]

    def put(p, v):
        if p[0] == "hfov":
            rig.hfov = v
        else:
            getattr(rig, p[0])[p[1]] = v

    best = mismatch(shots, grays, rig, plist)
    while step >= min_step:
        improved = False
        for p in params:
            old = get(p)
            for k in (-2, -1, -0.5, 0.5, 1, 2):
                v = old + k * step
                if (p[0] == "pitch" and not -90 <= v <= 90) or (p[0] == "hfov" and not 30 <= v <= 150):
                    continue
                put(p, v)
                e = mismatch(shots, grays, rig, plist)
                if e < best - 1e-6:
                    best, old, improved = e, v, True
                put(p, old)
        if not improved:
            step /= 2
    return best


def calibrate(shots: list[Shot], rig: Rig | None = None, width: int = 320, log=None) -> Rig:
    """Measure the field of view and each ring's pitch (and small yaw offsets), in stages so
    the unknowns can't trade off against each other: the level ring alone (field of view,
    level pitch), then each other ring against the level ring, then all together."""
    rig = rig or Rig()
    grays = [_gray(s.img, width) for s in shots]
    everything = pairs(shots)
    rings = {s.ring for s in shots}

    def among(*names):
        keep = set(names)
        return [(a, b) for a, b in everything if shots[a].ring in keep and shots[b].ring in keep]

    level_pairs = [(a, b) for a, b in everything if shots[a].ring == shots[b].ring == "level"]
    _descend(shots, grays, rig, level_pairs, [("hfov", None), ("pitch", "level")], 4.0)
    for ring, beside in (("up", "level"), ("down", "level"), ("zenith", "up"), ("nadir", "down")):
        if ring in rings:
            _descend(shots, grays, rig, among(ring, beside), [("pitch", ring), ("yaw_off", ring)], 4.0)
    params = [("hfov", None)] + [("pitch", r) for r in rig.pitch if r in rings]
    params += [("yaw_off", r) for r in rig.yaw_off if r in rings and r != "level"]
    best = _descend(shots, grays, rig, everything, params, 1.0)
    if log:
        log(f"  field of view {rig.hfov:.1f} deg; pitches " +
            ", ".join(f"{r} {v:.1f}" for r, v in rig.pitch.items() if r in rings) +
            f"; mismatch {best:.1f}")
    return rig


SHARP = 12  # blending: higher prefers the picture looking most straight at a spot (less ghosting)
FEATHER = 0.06  # ... fading out over this share of a picture's width at its edges


def colors(shots: list[Shot], rig: Rig, d: np.ndarray, skip_behind: bool = True):
    """Colors seen along directions d (n, 3): each picture that sees a direction samples it,
    weighted toward the picture most straight on it. Returns (n, 3) uint8 and a mask of the
    directions some picture saw."""
    acc = np.zeros((d.shape[0], 3), dtype=np.float32)
    wsum = np.zeros(d.shape[0], dtype=np.float32)
    mean = d.mean(axis=0)
    mean = mean / (np.linalg.norm(mean) or 1)
    for s in shots:
        cam = camera(s, rig)
        if skip_behind and len(d) > 1000 and float(mean @ cam[2]) < -0.3:
            continue  # (a picture looking away from this whole patch)
        h, w = s.img.shape[:2]
        f = focal(w, rig.hfov)
        px, py, z, ok = project(d, cam, w, h, f)
        if not ok.any():
            continue
        edge = np.minimum.reduce([px, w - 1 - px, py, h - 1 - py]) / (FEATHER * w)
        wt = np.where(ok, np.clip(edge, 0, 1) * np.clip(z, 0, 1) ** SHARP, 0).astype(np.float32)
        idx = np.nonzero(wt > 1e-12)[0]
        acc[idx] += sample(s.img, px[idx], py[idx]) * wt[idx, None]
        wsum[idx] += wt[idx]
    out = acc / np.maximum(wsum, 1e-30)[:, None]
    return np.clip(out, 0, 255).astype(np.uint8), wsum > 0


def panorama(shots: list[Shot], rig: Rig, width: int = 4096, band: int = 128) -> np.ndarray:
    """The equirectangular panorama (width x width/2, RGB uint8), in bands of rows."""
    height = width // 2
    out = np.zeros((height, width, 3), dtype=np.uint8)
    covered = np.zeros((height, width), dtype=bool)
    lon = ((np.arange(width) + 0.5) / width * 2 - 1) * math.pi
    for top in range(0, height, band):
        rows = np.arange(top, min(top + band, height))
        lat = (0.5 - (rows + 0.5) / height) * math.pi
        LON, LAT = np.meshgrid(lon, lat)
        d = np.stack([np.sin(LON) * np.cos(LAT), np.sin(LAT), np.cos(LON) * np.cos(LAT)], axis=-1).reshape(-1, 3)
        c, seen = colors(shots, rig, d, skip_behind=False)
        out[rows[0]:rows[-1] + 1] = c.reshape(len(rows), width, 3)
        covered[rows[0]:rows[-1] + 1] = seen.reshape(len(rows), width)
    return fill_gaps(out, covered)


# The cube the viewer draws from: six faces, each (normal, right, up) in the panorama's frame
# (x right, y up, z forward along the spot's first facing). Keep in step with Data.lua D.FACES.
FACES = {
    "F": ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
    "R": ((1, 0, 0), (0, 0, -1), (0, 1, 0)),
    "B": ((0, 0, -1), (-1, 0, 0), (0, 1, 0)),
    "L": ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
    "U": ((0, 1, 0), (1, 0, 0), (0, 0, -1)),
    "D": ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
}
CUBE_PAD = 0.08  # each tile reaches this far (in face units, a face is 2 across) past its quarter


def tile_bounds(ti: int, tj: int, pad: float = CUBE_PAD):
    """Face coordinates a (right) from a0 to a1 and b (up) from b0 to b1 a tile's image
    covers: quarter ti (0 left, 1 right), tj (0 top, 1 bottom) of the face, plus the pad."""
    a0, a1 = (-1.0, 0.0) if ti == 0 else (0.0, 1.0)
    b0, b1 = (0.0, 1.0) if tj == 0 else (-1.0, 0.0)
    return a0 - pad, a1 + pad, b0 - pad, b1 + pad


def tile_dirs(face: str, ti: int, tj: int, n: int, pad: float = CUBE_PAD) -> np.ndarray:
    """Directions of a tile image's pixels (row by row from the top), (n*n, 3)."""
    nrm, r, u = (np.array(v, dtype=float) for v in FACES[face])
    a_lo, a_hi, b_lo, b_hi = tile_bounds(ti, tj, pad)
    a = a_lo + (np.arange(n) + 0.5) / n * (a_hi - a_lo)
    b = b_hi - (np.arange(n) + 0.5) / n * (b_hi - b_lo)
    A, B = np.meshgrid(a, b)
    d = A.reshape(-1, 1) * r + B.reshape(-1, 1) * u + nrm
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def cube_tiles(shots: list[Shot], rig: Rig, size: int = 1024, pad: float = CUBE_PAD, fill=None,
               faces=None):
    """The 24 cube tiles {"F00": (size, size, 3) uint8, ...}, rendered straight from the
    pictures. `fill`: a gap-filled panorama to take directions no picture saw from."""
    out = {}
    for face in (faces or FACES):
        for ti in (0, 1):
            for tj in (0, 1):
                d = tile_dirs(face, ti, tj, size, pad)
                c, seen = colors(shots, rig, d)
                if fill is not None and not seen.all():
                    miss = ~seen
                    ph, pw = fill.shape[:2]
                    lon = np.arctan2(d[miss, 0], d[miss, 2])
                    lat = np.arcsin(np.clip(d[miss, 1], -1, 1))
                    px = np.clip((lon / math.pi + 1) / 2 * pw - 0.5, 0, pw - 1.001)
                    py = np.clip((0.5 - lat / math.pi) * ph - 0.5, 0, ph - 1.001)
                    c[miss] = sample(fill, px, py).astype(np.uint8)
                out[f"{face}{ti}{tj}"] = c.reshape(size, size, 3)
    return out


def fill_gaps(img: np.ndarray, covered: np.ndarray) -> np.ndarray:
    """Pixels no picture saw (between the up ring and the straight-up picture when the up
    view was saved too shallow): blended down each column from the nearest seen pixels above
    and below."""
    if covered.all() or not covered.any():
        return img
    out = img.copy()
    rows = np.arange(img.shape[0])
    for x in np.nonzero(~covered.all(axis=0))[0]:
        seen = covered[:, x]
        if seen.sum() < 2:
            continue
        for c in range(3):
            out[~seen, x, c] = np.interp(rows[~seen], rows[seen], img[seen, x, c]).astype(np.uint8)
    return out


def render(pano: np.ndarray, yaw: float, pitch: float, w: int, h: int, hfov: float) -> np.ndarray:
    """A pinhole picture rendered from a panorama (tests)."""
    f = focal(w, hfov)
    d, xs, ys = pixel_dirs(w, h, f, axes(yaw, pitch))
    ph, pw = pano.shape[:2]
    lon = np.arctan2(d[:, 0], d[:, 2])
    lat = np.arcsin(np.clip(d[:, 1], -1, 1))
    px = np.clip((lon / math.pi + 1) / 2 * pw - 0.5, 0, pw - 1.001)
    py = np.clip((0.5 - lat / math.pi) * ph - 0.5, 0, ph - 1.001)
    return sample(pano.astype(np.float32), px, py).reshape(h, w, 3).astype(np.uint8)
