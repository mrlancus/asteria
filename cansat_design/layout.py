"""Nest several canopy designs on one piece of fabric, then print the layout on A4.

Pick the designs (shape, spill hole, target speed) and how many of each; any design
marked "fill" is repeated until nothing more fits, so the fabric gets used up.
Packing is a bottom-left fill on a grid (default 5 mm cells): each piece (cut line +
half the cutting gap) is tried at 0°, 90°, 180° and 270°, and goes at the lowest, then
leftmost, free spot. Small pieces can land inside large spill holes. Gored canopies are
placed as a complete set of gores or not at all.

The layout is drawn full size in mm (SVG) and split into A4 pages with an overlap,
page labels and alignment marks, as SVG tiles and as one multi-page PDF.
"""

import io
import math
from dataclasses import dataclass, field

import numpy as np
from matplotlib.path import Path as MplPath
from scipy.signal import fftconvolve

from . import parachute as P
from .svg_export import A4, attachment_points, offset_polygon, _path, _svg

PAGE_MARGIN, PAGE_OVERLAP = 10.0, 10.0


@dataclass
class LayoutItem:
    shape: str
    spill_pct: float
    speed_m_s: float
    qty: int = 1            # complete parachutes wanted
    fill: bool = False      # after the fixed quantities, repeat this design until the fabric is full


@dataclass
class Placed:
    design: int             # index into Layout.designs
    copy: int               # which parachute of that design (1, 2, …)
    piece: int              # gore number (1…n) or 1
    finished: np.ndarray    # stitch outline, fabric mm (x right, y down from the top-left corner)
    cut: np.ndarray         # cut outline, fabric mm
    hole: tuple | None      # (cx, cy, finished radius, cut radius) for flat canopies
    marks: np.ndarray       # line attachment points, fabric mm


@dataclass
class Layout:
    width_mm: float
    length_mm: float
    designs: list                       # (label, Canopy, LayoutItem)
    placed: list = field(default_factory=list)
    counts: list = field(default_factory=list)
    unplaced: list = field(default_factory=list)   # (design index, how many fixed copies did not fit)

    @property
    def used_m2(self) -> float:
        return sum(_poly_area(p.cut) for p in self.placed) / 1e6 - sum(
            math.pi * p.hole[3] ** 2 for p in self.placed if p.hole) / 1e6

    @property
    def fabric_m2(self) -> float:
        return self.width_mm * self.length_mm / 1e6


def _poly_area(pts):
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * abs(float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)))


def _rot(pts, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return pts @ np.array([[c, s], [-s, c]])


def _raster(poly, lo, shape, res, hole=None):
    """Cells whose centre is inside poly (and not inside the hole circle)."""
    ny, nx = shape
    xs = lo[0] + (np.arange(nx) + 0.5) * res
    ys = lo[1] + (np.arange(ny) + 0.5) * res
    gx, gy = np.meshgrid(xs, ys)
    pts = np.column_stack([gx.ravel(), gy.ravel()])
    m = MplPath(poly).contains_points(pts).reshape(shape)
    if hole is not None:
        cx, cy, r = hole
        m &= (gx - cx) ** 2 + (gy - cy) ** 2 > r ** 2
    return m


@dataclass
class _Part:
    piece: int
    finished: np.ndarray        # mm, unit frame
    cut: np.ndarray
    hole: tuple | None          # (cx, cy, finished r, cut r)
    marks: np.ndarray


@dataclass
class _Unit:
    """What gets placed in one go: a flat canopy, or two gores nested nose-to-tail."""
    parts: list
    masks: list = field(default_factory=list)   # (deg, mask, lo) per rotation


def _moved(part, deg, shift, piece=None):
    hole = None
    if part.hole:
        c = _rot(np.array([part.hole[:2]]), deg)[0] + shift
        hole = (c[0], c[1], *part.hole[2:])
    return _Part(piece or part.piece, _rot(part.finished, deg) + shift, _rot(part.cut, deg) + shift,
                 hole, _rot(part.marks, deg) + shift)


def _masks(unit, gap, res, rotations):
    for deg in rotations:
        parts = [_moved(p, deg, np.zeros(2)) for p in unit.parts]
        grown = [offset_polygon(p.cut, gap / 2 + res * 0.71) for p in parts]   # conservative cell cover
        lo = np.min([g.min(axis=0) for g in grown], axis=0)
        hi = np.max([g.max(axis=0) for g in grown], axis=0)
        shape = (max(1, math.ceil((hi[1] - lo[1]) / res)), max(1, math.ceil((hi[0] - lo[0]) / res)))
        m = np.zeros(shape, dtype=bool)
        for p, g in zip(parts, grown):
            h = None
            if p.hole and p.hole[3] - gap / 2 - res > 0:
                h = (p.hole[0], p.hole[1], p.hole[3] - gap / 2 - res * 0.71)   # free cells inside the spill hole
            m |= _raster(g, lo, shape, res, h)
        unit.masks.append((deg, m, lo))


def _nest_pair(cut, gap):
    """x offset that puts a 180°-turned copy of a gore right beside it, edges parallel."""
    a = offset_polygon(cut, gap / 2)
    b0 = offset_polygon(_rot(cut, 180), gap / 2)
    step = 1.0
    lo = np.min([a.min(axis=0), b0.min(axis=0)], axis=0) - 2
    width = a[:, 0].max() - a[:, 0].min()
    for k in range(int(2 * width / step) + 2):
        dx = k * step
        b = b0 + [dx, 0]
        hi = np.max([a.max(axis=0), b.max(axis=0)], axis=0) + 2
        shape = (math.ceil((hi[1] - lo[1]) / step), math.ceil((hi[0] - lo[0]) / step))
        if not (_raster(a, lo, shape, step) & _raster(b, lo, shape, step)).any():
            return dx
    return 2 * width


def _units_for(canopy, pc, gap, res):
    seam = pc.seam_allowance_mm
    base = canopy.pieces[0] * 1000
    flat = canopy.n_pieces == 1
    centre = np.zeros(2) if flat else (base.min(axis=0) + base.max(axis=0)) / 2   # gores: centre on their box
    base = base - centre
    cut = offset_polygon(base, seam)
    marks = attachment_points(canopy, P.n_lines_for(pc, canopy)) * 1000 - centre
    rotations = (0, 90, 180, 270)
    if flat:
        hole = None
        if canopy.hole_d_m > 0:
            r_fin = canopy.hole_d_m * 500
            hole = (0.0, 0.0, r_fin, max(r_fin - seam, 0.0))
        u = _Unit([_Part(1, base, cut, hole, marks)])
        _masks(u, gap, res, rotations)
        return [u]
    one = _Part(1, base, cut, None, marks)
    dx = _nest_pair(cut, gap)
    units = []
    for k in range(0, canopy.n_pieces, 2):
        parts = [_moved(one, 0, np.zeros(2), k + 1)]
        if k + 1 < canopy.n_pieces:
            parts.append(_moved(one, 180, np.array([dx, 0.0]), k + 2))
        u = _Unit(parts)
        _masks(u, gap, res, rotations)
        units.append(u)
    return units


def _fit(occ, mask):
    """Lowest-then-leftmost free (row, col) for mask in occ, or None."""
    H, W = occ.shape
    h, w = mask.shape
    if h > H or w > W:
        return None
    ov = fftconvolve(occ.astype(float), mask[::-1, ::-1].astype(float), mode="valid")
    free = np.argwhere(ov < 0.5)
    if not len(free):
        return None
    r = free[:, 0].min()
    row = free[free[:, 0] == r]
    return int(r), int(row[:, 1].min())


def _place_set(occ, units, res):
    """Try to place every piece of one parachute; return placements or None (occ unchanged)."""
    trial = occ.copy()
    done = []
    for u in units:
        best = None
        for deg, mask, lo in u.masks:
            pos = _fit(trial, mask)
            if pos and (best is None or pos < best[0]):
                best = (pos, deg, mask, lo)
        if best is None:
            return None
        (r, c), deg, mask, lo = best
        trial[r:r + mask.shape[0], c:c + mask.shape[1]] |= mask
        shift = np.array([c * res, r * res]) - lo
        done.extend(_moved(p, deg, shift) for p in u.parts)
    occ[:] = trial
    return done


def build_layout(cfg, items, width_mm=1000.0, length_mm=2000.0, gap_mm=6.0, edge_mm=10.0,
                 res_mm=5.0, max_fill=200) -> Layout:
    from .atmosphere import ground_density
    pc = cfg.parachute
    rho = ground_density(cfg.air)
    designs, sets = [], []
    for di, it in enumerate(items):
        c = P.size_canopy(pc, cfg.mass.design_mass_kg, rho, it.speed_m_s, shape=it.shape, spill_pct=it.spill_pct)
        label = (f"{code(di)}: {P.SHAPES[it.shape].label} {c.width_m * 100:.1f} cm, "
                 f"hole {it.spill_pct:.0f} %, {it.speed_m_s:g} m/s")
        designs.append((label, c, it))
        sets.append(_units_for(c, pc, gap_mm, res_mm))
    lay = Layout(width_mm, length_mm, designs, counts=[0] * len(items))

    H, W = math.ceil(length_mm / res_mm), math.ceil(width_mm / res_mm)
    occ = np.zeros((H, W), dtype=bool)
    e = max(0, math.ceil((edge_mm - gap_mm / 2) / res_mm))
    if e:
        occ[:e, :] = occ[-e:, :] = occ[:, :e] = occ[:, -e:] = True

    def put(di):
        got = _place_set(occ, sets[di], res_mm)
        if got is None:
            return False
        lay.counts[di] += 1
        for p in got:
            lay.placed.append(Placed(di, lay.counts[di], p.piece, p.finished, p.cut, p.hole, p.marks))
        return True

    # Fixed quantities first, biggest canopies first (packs better)
    order = sorted(range(len(items)), key=lambda i: -designs[i][1].gross_area_m2)
    for di in order:
        missing = 0
        for _ in range(max(0, int(items[di].qty))):
            if not put(di):
                missing += 1
        if missing:
            lay.unplaced.append((di, missing))
    # Then fill: round-robin over the fill designs until none fits
    active = [i for i in order if items[i].fill]
    n = 0
    while active and n < max_fill:
        for di in list(active):
            if put(di):
                n += 1
            else:
                active.remove(di)
    return lay


# ---------------------------------------------------------------- drawing

def code(di):
    """Design letter: A…Z, then AA, AB…"""
    return chr(65 + di) if di < 26 else chr(64 + di // 26) + chr(65 + di % 26)


def piece_tag(lay, p):
    """Text written on each piece, e.g. 'C2 hex 25 %' or 'F1 cone 0 % gore 3/8'."""
    _, c, it = lay.designs[p.design]
    t = f"{code(p.design)}{p.copy} {P.SHORT.get(it.shape, it.shape)} {it.spill_pct:g} %"
    return t + (f" gore {p.piece}/{c.n_pieces}" if c.n_pieces > 1 else "")


COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#8a5cd1", "#d1497f", "#6b6a64", "#0f7a32"]


def layout_body(lay: Layout, labels=True) -> str:
    """SVG elements of the whole fabric, full size in mm (origin at the fabric's top-left)."""
    W, L = lay.width_mm, lay.length_mm
    els = [f'<rect x="0" y="0" width="{W:.1f}" height="{L:.1f}" fill="none" stroke="#999" '
           f'stroke-width="0.6" stroke-dasharray="6,3"/>']
    for p in lay.placed:
        col = COLOURS[p.design % len(COLOURS)]
        els.append(f'<path d="{_path(p.cut)}" fill="{col}" fill-opacity="0.08" stroke="#000" stroke-width="0.4"/>')
        els.append(f'<path d="{_path(p.finished)}" fill="none" stroke="{col}" stroke-width="0.3" stroke-dasharray="3,2"/>')
        if p.hole:
            cx, cy, rf, rc = p.hole
            els.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{rf:.2f}" fill="none" stroke="{col}" '
                       f'stroke-width="0.3" stroke-dasharray="3,2"/>')
            if rc > 0:
                els.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{rc:.2f}" fill="#fff" stroke="#000" stroke-width="0.4"/>')
        for x, y in p.marks:
            els.append(f'<path d="M {x - 3:.2f},{y:.2f} L {x + 3:.2f},{y:.2f} M {x:.2f},{y - 3:.2f} '
                       f'L {x:.2f},{y + 3:.2f}" stroke="#e34948" stroke-width="0.4"/>')
        if labels:
            cx, cy = p.finished.mean(axis=0)
            if p.hole:
                cy += p.hole[2] + 8
            n = lay.designs[p.design][1].n_pieces
            tag = piece_tag(lay, p)
            els.append(f'<text x="{cx:.1f}" y="{cy:.1f}" font-family="sans-serif" font-size="6" '
                       f'text-anchor="middle" fill="#000">{tag}</text>')
    return "\n".join(els)


def layout_svg(lay: Layout) -> str:
    return _svg(layout_body(lay), lay.width_mm, lay.length_mm)


def page_grid(lay: Layout):
    pw, ph = A4[0] - 2 * PAGE_MARGIN, A4[1] - 2 * PAGE_MARGIN
    nx = max(1, math.ceil((lay.width_mm - PAGE_OVERLAP) / (pw - PAGE_OVERLAP)))
    ny = max(1, math.ceil((lay.length_mm - PAGE_OVERLAP) / (ph - PAGE_OVERLAP)))
    return pw, ph, nx, ny


def _cross(x, y, s=4):
    return f'<path d="M {x - s:.1f},{y:.1f} L {x + s:.1f},{y:.1f} M {x:.1f},{y - s:.1f} L {x:.1f},{y + s:.1f}" ' \
           f'stroke="#000" stroke-width="0.25"/>'


def a4_tiles(lay: Layout) -> dict:
    """{filename: svg} – one A4 page per tile, row by row, with 10 mm overlap."""
    body = layout_body(lay)
    pw, ph, nx, ny = page_grid(lay)
    files = {}
    for r in range(ny):
        for c in range(nx):
            x0, y0 = c * (pw - PAGE_OVERLAP), r * (ph - PAGE_OVERLAP)
            m, o = PAGE_MARGIN, PAGE_OVERLAP
            marks = [_cross(m, m), _cross(m + pw, m), _cross(m, m + ph), _cross(m + pw, m + ph),
                     _cross(m + o, m + o), _cross(m + pw - o, m + o), _cross(m + o, m + ph - o), _cross(m + pw - o, m + ph - o)]
            page = (f'<defs><clipPath id="c"><rect x="{m}" y="{m}" width="{pw}" height="{ph}"/></clipPath></defs>\n'
                    f'<g clip-path="url(#c)"><g transform="translate({m - x0:.2f},{m - y0:.2f})">\n{body}\n</g></g>\n'
                    f'<rect x="{m}" y="{m}" width="{pw}" height="{ph}" fill="none" stroke="#999" stroke-width="0.2" stroke-dasharray="1,1"/>\n'
                    + "\n".join(marks) +
                    f'\n<text x="{m}" y="{m - 3}" font-family="sans-serif" font-size="3.5">Page R{r + 1}C{c + 1} '
                    f'(row {r + 1} of {ny}, column {c + 1} of {nx}) – overlap {o:.0f} mm, line up the crosses</text>'
                    f'\n<text x="{m}" y="{A4[1] - 4}" font-family="sans-serif" font-size="3">Print at 100 % '
                    f'(actual size). 50 mm check: </text>'
                    f'<path d="M {m + 55},{A4[1] - 5} L {m + 105},{A4[1] - 5}" stroke="#000" stroke-width="0.4"/>')
            files[f"layout_A4_R{r + 1:02d}C{c + 1:02d}.svg"] = _svg(page, *A4)
    return files


def a4_pdf(lay: Layout) -> bytes:
    """All A4 pages in one PDF, at true scale, plus an index page first."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import Circle, Polygon, Rectangle

    pw, ph, nx, ny = page_grid(lay)
    mm = 1 / 25.4
    buf = io.BytesIO()

    def draw(ax, lw=1.0, text=True, view=None):
        ax.add_patch(Rectangle((0, 0), lay.width_mm, lay.length_mm, fill=False, ec="#999", lw=0.6 * lw, ls="--"))
        for p in lay.placed:
            if view:
                lo, hi = p.cut.min(axis=0), p.cut.max(axis=0)
                if hi[0] < view[0] or lo[0] > view[2] or hi[1] < view[1] or lo[1] > view[3]:
                    continue
            col = COLOURS[p.design % len(COLOURS)]
            ax.add_patch(Polygon(p.cut, closed=True, fc=col, alpha=1, fill=False, ec="#000", lw=0.6 * lw))
            ax.add_patch(Polygon(p.finished, closed=True, fill=False, ec=col, lw=0.5 * lw, ls=(0, (4, 3))))
            if p.hole:
                cx, cy, rf, rc = p.hole
                ax.add_patch(Circle((cx, cy), rf, fill=False, ec=col, lw=0.5 * lw, ls=(0, (4, 3))))
                if rc > 0:
                    ax.add_patch(Circle((cx, cy), rc, fill=False, ec="#000", lw=0.6 * lw))
            ax.plot(p.marks[:, 0], p.marks[:, 1], "+", color="#e34948", ms=6 * lw, mew=0.6 * lw)
            if text:
                cx, cy = p.finished.mean(axis=0)
                if p.hole:
                    cy += p.hole[2] + 8
                n = lay.designs[p.design][1].n_pieces
                ax.text(cx, cy, piece_tag(lay, p),
                        ha="center", va="center", fontsize=7, clip_on=True)

    with PdfPages(buf) as pdf:
        # Index page: whole layout scaled, with the page grid
        fig = plt.figure(figsize=(A4[0] * mm, A4[1] * mm))
        ax = fig.add_axes([0.08, 0.31, 0.84, 0.66])
        draw(ax, lw=0.4, text=False)
        for r in range(ny):
            for c in range(nx):
                x0, y0 = c * (pw - PAGE_OVERLAP), r * (ph - PAGE_OVERLAP)
                ax.add_patch(Rectangle((x0, y0), pw, ph, fill=False, ec="#2a78d6", lw=0.3))
                ax.text(x0 + pw / 2, y0 + ph / 2, f"R{r + 1}C{c + 1}", ha="center", va="center", fontsize=5, color="#2a78d6")
        ax.set_xlim(-20, lay.width_mm + 20)
        ax.set_ylim(lay.length_mm + 20, -20)
        ax.set_aspect("equal")
        ax.axis("off")
        lines = [f"Fabric {lay.width_mm:.0f} × {lay.length_mm:.0f} mm ({lay.fabric_m2:.2f} m²) – "
                 f"{lay.used_m2 / lay.fabric_m2:.0%} used, {nx * ny} A4 pages ({ny} rows × {nx} columns)"]
        lines += [f"{lbl} – × {n}" for (lbl, _, _), n in zip(lay.designs, lay.counts)]
        lines += ["Print every page at 100 % (actual size). Trim nothing: overlap pages by 10 mm and line up the crosses.",
                  "Solid = cut, dashed = stitch line, red + = line attachment. Generated by cansat_design (Claude Code)."]
        step = min(0.016, 0.27 / max(len(lines), 1))
        for i, t in enumerate(lines):
            fig.text(0.08, 0.28 - i * step, t, fontsize=6 if step >= 0.012 else 5)
        pdf.savefig(fig)
        plt.close(fig)

        for r in range(ny):
            for c in range(nx):
                x0, y0 = c * (pw - PAGE_OVERLAP), r * (ph - PAGE_OVERLAP)
                fig = plt.figure(figsize=(A4[0] * mm, A4[1] * mm))
                m = PAGE_MARGIN
                ax = fig.add_axes([m / A4[0], m / A4[1], pw / A4[0], ph / A4[1]])
                draw(ax, view=(x0 - 10, y0 - 10, x0 + pw + 10, y0 + ph + 10))
                ax.set_xlim(x0, x0 + pw)
                ax.set_ylim(y0 + ph, y0)
                ax.set_xticks([]); ax.set_yticks([])
                for s in ax.spines.values():
                    s.set_edgecolor("#999"); s.set_linestyle(":"); s.set_linewidth(0.4)
                o = PAGE_OVERLAP
                for (px, py) in [(x0 + o, y0 + o), (x0 + pw - o, y0 + o), (x0 + o, y0 + ph - o), (x0 + pw - o, y0 + ph - o)]:
                    ax.plot(px, py, "+", color="#000", ms=10, mew=0.4)
                fig.text(m / A4[0], 1 - 6 / A4[1], f"Page R{r + 1}C{c + 1} (row {r + 1} of {ny}, column {c + 1} of {nx}) "
                         f"– overlap {o:.0f} mm with neighbours, line up the crosses", fontsize=7)
                fig.text(m / A4[0], 4 / A4[1], "Print at 100 % (actual size). This bar is 50 mm:", fontsize=6)
                fig.add_artist(plt.Line2D([(m + 70) / A4[0], (m + 120) / A4[0]], [5 / A4[1], 5 / A4[1]],
                                          color="#000", lw=0.8))
                pdf.savefig(fig)
                plt.close(fig)
    return buf.getvalue()
