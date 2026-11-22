"""Reusable paper templates – far fewer pages than printing the whole fabric layout.

Every flat canopy here is symmetric, so one template does many canopies:
- square, hexagon, octagon, dodecagon, circle and both cruciforms: a QUARTER template.
  Fold the fabric in four, put the template's corner on the folded corner, cut through
  all four layers;
- pentagon: a HALF template on a single fold;
- gored canopies: one gore template, traced as many times as there are gores.
Designs of the same shape share one template with nested outlines, one per design (like
a multi-size sewing pattern), labelled with the design letter. Templates are packed onto
A4 pages; one that is too big for a page is split across pages with overlap marks.

Page 1 is a cutting map: the fabric layout to scale with a 10 cm grid, so each piece's
position can be marked on the fabric with a tape measure and chalk. Cut out a rough
rectangle round each piece, then fold and cut it with the template.
Print on card (or glue to cereal-box card) and the templates can be reused.
"""

import io
import math

import numpy as np

from . import parachute as P
from .layout import COLOURS, PAGE_MARGIN, code
from .svg_export import A4, attachment_points, offset_polygon

QUARTER = {"flat_hexagon", "flat_circle", "flat_square", "flat_octagon", "flat_dodecagon",
           "cruciform", "cruciform_long"}
HALF = {"flat_pentagon"}
GAP_MM = 6


def _clip(poly, keep):
    """Sutherland–Hodgman clip of a closed polygon by one half-plane, keep(p) -> signed distance ≥ 0."""
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        da, db = keep(a), keep(b)
        if da >= 0:
            out.append(a)
        if (da >= 0) != (db >= 0):
            t = da / (da - db)
            out.append(a + t * (b - a))
    return np.array(out) if out else np.zeros((0, 2))


def _region(poly, kind):
    if kind == "quarter":
        poly = _clip(_clip(poly, lambda p: p[0]), lambda p: p[1])
    elif kind == "half":
        poly = _clip(poly, lambda p: p[0])
    return poly


def _open_edges(poly, kind, eps=1e-6):
    """Edges of the clipped polygon that are NOT on a fold line (those are drawn as cut/stitch lines)."""
    segs = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        on_y_fold = abs(a[0]) < eps and abs(b[0]) < eps
        on_x_fold = kind == "quarter" and abs(a[1]) < eps and abs(b[1]) < eps
        if not (on_y_fold or on_x_fold):
            segs.append((a, b))
    return segs


class Template:
    """One shape family: nested outlines for each design, in mm, y up, fold corner at the origin."""

    def __init__(self, shape, entries, pc):
        self.shape = shape
        self.kind = "quarter" if shape in QUARTER or shape == "quarter" else "half" if shape in HALF else "gore"
        self.lines = []          # (colour, style, segments)
        self.arcs = []           # (colour, style, radius)
        self.marks = []
        self.labels = []         # (x, y, text, colour)
        self.notes = []
        seam = pc.seam_allowance_mm
        single = len(entries) == 1
        for k, (di, c, it, count) in enumerate(entries):
            col = COLOURS[di % len(COLOURS)]
            fin = c.pieces[0] * 1000
            if self.kind == "gore":
                fin = fin - fin.min(axis=0) + seam
            cut = offset_polygon(fin, seam)
            for poly, style in ((cut, "cut"), (fin, "stitch")):
                r = _region(poly, self.kind) if self.kind != "gore" else poly
                segs = _open_edges(r, self.kind) if self.kind != "gore" else \
                    [(r[i], r[(i + 1) % len(r)]) for i in range(len(r))]
                self.lines.append((col, style, segs))
            if self.kind != "gore" and c.hole_d_m > 0:
                rf = c.hole_d_m * 500
                self.arcs.append((col, "stitch", rf))
                if rf - seam > 0:
                    self.arcs.append((col, "cut", rf - seam))
            m = attachment_points(c, P.n_lines_for(pc, c)) * 1000
            if self.kind == "gore":
                m = m - (c.pieces[0] * 1000).min(axis=0) + seam
            else:
                m = m[(m[:, 0] > -1e-6) & ((m[:, 1] > -1e-6) | (self.kind == "half"))]
            self.marks += [tuple(x) for x in m]
            # label on this design's cut line, spread along it so nested labels don't collide
            segs = self.lines[-2][2]
            if segs:
                a, b = segs[min(len(segs) - 1, int((k + 0.5) / len(entries) * len(segs)))]
                self.labels.append(((a[0] + b[0]) / 2 + 1.5, (a[1] + b[1]) / 2 + 1.5, code(di), col))
            if not single:                       # nested: colour the cut lines too, so each design is traceable
                self.lines[-2] = (col, "cut_c", self.lines[-2][2])
            n_cut = count * (c.n_pieces if self.kind == "gore" else 1)
            hole = f", hole {it.spill_pct:g} % ({c.hole_d_m * 1000:.0f} mm)" if c.hole_d_m else ", no hole"
            self.notes.append((f"{code(di)}: {P.SHORT.get(it.shape, it.shape)} {c.width_m * 100:.1f} cm{hole} – cut {n_cut}", col))
        pts = [p for _, _, segs in self.lines for s in segs for p in s] + [(r, r) for _, _, r in self.arcs]
        pts = np.array(pts)
        self.lo = np.minimum(pts.min(axis=0), 0) if self.kind != "gore" else pts.min(axis=0)
        self.hi = pts.max(axis=0) + 8          # room for labels
        if self.kind != "gore":
            self.lo = np.array([0.0, self.lo[1] if self.kind == "half" else 0.0])
        self.w, self.h = self.hi - self.lo
        self.text_h = 10 + math.ceil(len(self.notes) / 3) * 3.2
        how = {"quarter": "Fold the fabric in four; corner ★ on the folded corner; cut all 4 layers.",
               "half": "Fold the fabric once; edge ★ on the fold; cut both layers.",
               "gore": "Trace and cut once per gore (cut count below includes every gore)."}[self.kind]
        name = "Flat canopies (all shapes that fold in four)" if shape == "quarter" else P.SHAPES[shape].label
        self.title = f"{name} – {self.kind} template. {how}" + ("" if single else " Highlight your design's line first.")


def build_templates(lay, pc):
    fam = {}
    seen = set()
    for di, ((lbl, c, it), n) in enumerate(zip(lay.designs, lay.counts)):
        if n == 0:
            continue
        key = (it.shape, round(it.spill_pct, 3), round(it.speed_m_s, 3))
        if key in seen:                         # identical design (e.g. spares) – merge the count
            for t in fam["quarter" if it.shape in QUARTER else it.shape]:
                if (t[2].shape, round(t[2].spill_pct, 3), round(t[2].speed_m_s, 3)) == key:
                    t[3] += n
            continue
        seen.add(key)
        fam.setdefault("quarter" if it.shape in QUARTER else it.shape, []).append([di, c, it, n])
    return [Template(s, e, pc) for s, e in fam.items()]


def _pack(templates, pw, ph):
    """Shelf-pack template boxes onto pages. Returns [(page, x, y, template, view)], n pages.
    A template larger than a page is split into tiles (view = its mm window)."""
    boxes = []
    for t in templates:
        W, H = t.w, t.h + t.text_h
        if W <= pw and H <= ph:
            boxes.append((W, H, t, None))
        else:
            ov = 10.0
            nx = max(1, math.ceil((t.w - ov) / (pw - ov)))
            ny = max(1, math.ceil((t.h + t.text_h - ov) / (ph - ov)))
            for r in range(ny):
                for c in range(nx):
                    x0 = t.lo[0] + c * (pw - ov)
                    ytop = t.hi[1] - r * (ph - ov)
                    boxes.append((min(pw, t.w - c * (pw - ov)), ph, t, (x0, ytop, r, c, ny, nx)))
    boxes.sort(key=lambda b: -b[1])
    placed, page, x, y, shelf = [], 0, 0.0, 0.0, 0.0
    for W, H, t, view in boxes:
        if x + W > pw:
            x, y, shelf = 0.0, y + shelf + GAP_MM, 0.0
        if y + H > ph:
            page, x, y, shelf = page + 1, 0.0, 0.0, 0.0
        placed.append((page, x, y, t, view))
        x += W + GAP_MM
        shelf = max(shelf, H)
    return placed, page + 1


def templates_pdf(lay, pc) -> tuple[bytes, int]:
    """Cutting map + packed reusable templates. Returns (pdf bytes, number of pages)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import Arc, Polygon, Rectangle

    m = PAGE_MARGIN
    pw, ph = A4[0] - 2 * m, A4[1] - 2 * m
    temps = build_templates(lay, pc)
    placed, n_pages = _pack(temps, pw, ph)
    inch = 1 / 25.4
    buf = io.BytesIO()
    ls = {"cut": ("#000", "-", 0.7), "cut_c": (None, "-", 0.7), "stitch": (None, (0, (4, 3)), 0.4)}

    with PdfPages(buf) as pdf:
        # ---- page 1: cutting map with a 10 cm grid
        fig = plt.figure(figsize=(A4[0] * inch, A4[1] * inch))
        ax = fig.add_axes([0.1, 0.27, 0.82, 0.69])
        W, L = lay.width_mm, lay.length_mm
        for g in np.arange(0, W + 1, 100):
            ax.plot([g, g], [0, L], color="#cfd8e6", lw=0.3)
            ax.text(g, -15, f"{g / 10:.0f}", ha="center", fontsize=4.5, color="#2a78d6")
        for g in np.arange(0, L + 1, 100):
            ax.plot([0, W], [g, g], color="#cfd8e6", lw=0.3)
            ax.text(-15, g, f"{g / 10:.0f}", ha="right", va="center", fontsize=4.5, color="#2a78d6")
        ax.add_patch(Rectangle((0, 0), W, L, fill=False, ec="#555", lw=0.6))
        for p in lay.placed:
            col = COLOURS[p.design % len(COLOURS)]
            ax.add_patch(Polygon(p.cut, closed=True, fc=col, alpha=0.15, ec=col, lw=0.4))
            lo, hi = p.cut.min(axis=0), p.cut.max(axis=0)
            ax.add_patch(Rectangle(lo, *(hi - lo), fill=False, ec="#888", lw=0.25, ls=":"))
            if p.piece <= 1 or lay.designs[p.design][1].n_pieces == 1 or p.piece % 2 == 1:
                ax.text(*p.cut.mean(axis=0), f"{code(p.design)}{p.copy}", ha="center", va="center", fontsize=4)
        ax.set_xlim(-40, W + 10); ax.set_ylim(L + 10, -30); ax.set_aspect("equal"); ax.axis("off")
        lines = [f"CUTTING MAP – fabric {W / 10:.0f} × {L / 10:.0f} cm, grid every 10 cm (numbers in cm from the top-left corner).",
                 "1. Mark each dotted box on the fabric with chalk and a tape measure, and cut the rough rectangles out.",
                 "2. Fold each rectangle as its template says, put the template on the fold, pin, and cut along the line for that design.",
                 "3. Mark the dashed stitch line and the red + line points (prick through the paper with a pin).",
                 f"Templates: {len(temps)} shape families on {n_pages} A4 page{'s' if n_pages != 1 else ''} "
                 f"(instead of {math.ceil((W - 10) / 180) * math.ceil((L - 10) / 267)} for the full layout). Print on card to reuse them.",
                 "Print at 100 % (actual size) and check the 50 mm bar on each page. Generated by cansat_design (Claude Code)."]
        for i, t in enumerate(lines):
            fig.text(0.08, 0.22 - i * 0.02, t, fontsize=6)
        pdf.savefig(fig)
        plt.close(fig)

        # ---- template pages
        for page in range(n_pages):
            fig = plt.figure(figsize=(A4[0] * inch, A4[1] * inch))
            ax = fig.add_axes([m / A4[0], m / A4[1], pw / A4[0], ph / A4[1]])
            ax.set_xlim(0, pw); ax.set_ylim(ph, 0); ax.axis("off")
            for pg, x, y, t, view in placed:
                if pg != page:
                    continue
                if view is None:
                    ox, oy, top, clipbox = x - t.lo[0], y + t.hi[1], 0, None
                else:
                    x0, ytop, r, c, ny, nx = view
                    ox, oy = x - x0, y + ytop
                    clipbox = Rectangle((x, y), min(pw - x, t.w), ph - y, transform=ax.transData)
                tf = lambda pts: np.column_stack([ox + np.asarray(pts)[:, 0], oy - np.asarray(pts)[:, 1]])
                arts = []
                for col, style, segs in t.lines:
                    ec, dash, lw = ls[style]
                    for a, b in segs:
                        q = tf([a, b])
                        arts += ax.plot(q[:, 0], q[:, 1], color=ec or col, ls=dash, lw=lw)
                for col, style, rad in t.arcs:
                    ec, dash, lw = ls[style]
                    c0 = tf([(0, 0)])[0]
                    span = (0, 90) if t.kind == "quarter" else (-90, 90)
                    a = Arc(c0, 2 * rad, 2 * rad, theta1=-span[1], theta2=-span[0], color=ec or col, ls=dash, lw=lw)
                    ax.add_patch(a); arts.append(a)
                if t.marks:
                    q = tf(t.marks)
                    arts += ax.plot(q[:, 0], q[:, 1], "+", color="#e34948", ms=7, mew=0.7)
                for lx, ly, txt, col in t.labels:
                    q = tf([(lx, ly)])[0]
                    arts.append(ax.text(q[0], q[1], txt, color=col, fontsize=7, fontweight="bold"))
                if t.kind != "gore":                                  # fold lines
                    top_y = t.hi[1] - 6
                    q = tf([(0, t.lo[1] if t.kind == "half" else 0), (0, top_y)])
                    arts += ax.plot(q[:, 0], q[:, 1], color="#2a78d6", lw=1.2, ls="-.")
                    arts.append(ax.text(q[1, 0] + 1.5, q[1, 1] + 4, "FOLD", color="#2a78d6", fontsize=6, rotation=-90))
                    if t.kind == "quarter":
                        q = tf([(0, 0), (t.hi[0] - 6, 0)])
                        arts += ax.plot(q[:, 0], q[:, 1], color="#2a78d6", lw=1.2, ls="-.")
                        arts.append(ax.text(q[1, 0] - 12, q[1, 1] - 1.5, "FOLD", color="#2a78d6", fontsize=6))
                        c0 = tf([(0, 0)])[0]
                        arts.append(ax.text(c0[0] + 1.5, c0[1] - 1.5, "★", color="#2a78d6", fontsize=9))
                    else:
                        c0 = tf([(0, 0)])[0]
                        arts.append(ax.text(c0[0] + 1.5, c0[1], "★", color="#2a78d6", fontsize=9))
                # notes under the template (only on its first tile)
                if view is None or (view[2] == view[4] - 1 and view[3] == 0):
                    ny0 = (y + t.h + 4) if view is None else (y + ph - t.text_h + 4)
                    arts.append(ax.text(x, ny0, t.title, fontsize=5.5, va="top", wrap=True))
                    for i, (note, col) in enumerate(t.notes):
                        arts.append(ax.text(x + (i % 3) * 62, ny0 + 4 + (i // 3) * 3.2, note, color=col, fontsize=4.8, va="top"))
                if view is not None:
                    arts.append(ax.text(x, y + 3, f"part R{view[2] + 1}C{view[3] + 1} of {view[4]} × {view[5]} – "
                                        "overlap 10 mm", fontsize=5.5, color="#555"))
                if clipbox is not None:
                    for a in arts:
                        a.set_clip_path(clipbox)
            fig.text(m / A4[0], 1 - 6 / A4[1], f"Templates – page {page + 1} of {n_pages}. Solid = cut, dashed = stitch, "
                     "blue dash-dot = fold, red + = line attachment.", fontsize=6.5)
            fig.text(m / A4[0], 4 / A4[1], "Print at 100 % (actual size). This bar is 50 mm:", fontsize=6)
            fig.add_artist(plt.Line2D([(m + 70) / A4[0], (m + 120) / A4[0]], [5 / A4[1], 5 / A4[1]], color="#000", lw=0.8))
            pdf.savefig(fig)
            plt.close(fig)
    return buf.getvalue(), n_pages + 1
