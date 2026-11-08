# 灯をともせ: a harbour town switches off its old lighthouse at midnight. The old keeper lies in the hospital on the hill.
# He gives his grandson the key. The boy runs through the summer festival and up the cliff stairs, and he lights the
# lamp one last time on the chorus. The beam sweeps the town while it dances. At dawn the lamp goes dark, and the chair
# by the hospital window is empty.
# The plates never move. Footprints guard every path. Every runner faces the way that it moves.
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pixkit import INK, Captions, Occlusion, Sprite, bayer_field, contact_shadow
from studio_paths import font_path

BEAM = np.array([255, 236, 170], np.float32)
LAMP_M, LAMP_P, LAMP_W = (264, 82), (322, 135), (220, 185)

CHAIR = (227, 249)
BOY_ROOM = (176, 256)
EXIT = (140, 276)
STAIRS = [(196, 262), (210, 258), (232, 228), (212, 212), (200, 195), (225, 162), (250, 159)]
STAIR_CLIPS = ["b_r7_r", "b_r7_ur", "b_r7_ul", "b_r7_ul", "b_r7_ur", "b_r7_r"]
DOWN = [(215, 167), (222, 170), (200, 195), (212, 212), (232, 228), (210, 258), (196, 262)]
DOWN_CLIPS = ["b_dn_r", "b_dn_l", "b_dn_r", "b_dn_r", "b_dn_l", "b_dn_w"]
GALLERY = (250, 95)
CLIFF = (215, 167)
RUN = [(75, 270), (150, 279), (240, 272), (252, 216), (283, 183)]
RUN_CLIPS = ["b_run_r", "b_run_r", "b_run_u", "b_run_u"]
RING_C, RING_R = (177, 243), (50, 19)
FOLK = ["folk_a", "folk_b", "folk_c", "folk_d"]
MOVES = ["d_sway", "d_joget", "d_fest"]


def make(ctx):
    G, fps, brief, A, root = ctx["grid"], ctx["fps"], ctx["brief"], ctx["a"], ctx["root"]
    paper = np.array(brief["paper"], np.uint8)
    beats = np.array(A["beats"])
    bayer = bayer_field(G)
    Y, X = np.mgrid[:G, :G]
    caps = Captions(brief["lines"], paper, top_font=(font_path("msgothic.ttc"), 16), low_font=(font_path("msgothic.ttc"), 12))
    shapes = json.loads((root / "occluders.json").read_text(encoding="utf-8"))

    def beat(t):
        return float(beats[np.argmin(np.abs(beats - t))])

    T_FEST, T_CLIMB, T_HIT, T_WATCH, T_RAISE, T_DANCE, T_DAWN, T_EMPTY, T_KEY = (
        beat(10.43), beat(23.0), brief["hit"], beat(43.07), beat(49.57), beat(56.03), beat(69.23), beat(79.97), beat(89.57))
    T_OFF = 70.86  # The lamp goes dark on 消える.
    T_WALK, T_QUAY = beat(95.0), 104.6  # The beats end at 99 s, so the walk ends on a set time.
    T_DOOR = T_HIT - 1.0

    def plate(name, occ):
        d = np.asarray(Image.open(root / f"plates/{name}-360.png").convert("RGB")).copy()
        is_paper = (np.abs(d.astype(int) - paper.astype(int)).sum(axis=2) < 24) | (d.astype(int).sum(axis=2) > 720)
        d[is_paper] = paper
        return {"name": name, "day": d, "paper": is_paper, "occ": Occlusion(root, occ)}

    P = {"misaki": plate("misaki", "misaki"), "misaki_asa": plate("misaki_asa", "misaki"), "matsuri": plate("matsuri", "matsuri"),
         "byoin": plate("byoin", "byoin"), "byoin_asa": plate("byoin_asa", "byoin")}
    sprites = {}

    def S(folder, name):
        if (folder, name) not in sprites:
            sprites[(folder, name)] = Sprite(root, name, folder)
        return sprites[(folder, name)]

    def clearance(name, x, y):
        solids = [o["footprint"] for o in shapes.get(name, []) if "footprint" in o]
        return min((np.hypot((x - cx) / rx, (y - cy) / ry) for cx, cy, rx, ry in solids), default=9.0)

    def path_points(pts, step=3):
        out = []
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = max(int(np.hypot(x1 - x0, y1 - y0) / step), 1)
            out += [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n + 1)]
        return out

    def guard(name, pts):
        low = float(min(clearance(name, x, y) for x, y in pts))
        print(f"Footprint clearance on {name}, with 1.0 at the object edge:", round(low, 2), flush=True)
        if low < 1.0:
            raise SystemExit(f"A person stands inside a solid object on {name}: {low:.2f}")

    ring = [(RING_C[0] + RING_R[0] * np.cos(a), RING_C[1] + RING_R[1] * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 12, endpoint=False)]
    guard("byoin", [CHAIR, BOY_ROOM] + path_points([BOY_ROOM, EXIT]))
    guard("matsuri", ring + path_points(RUN))
    guard("misaki", path_points(STAIRS) + path_points(DOWN) + [CLIFF])
    checked = set()

    def heading(spr, dx, dy):
        """Stops the render if a clip runs against its path. A backward runner reads as a moonwalk."""
        if spr.name in checked or np.hypot(dx, dy) < 8:
            return
        p0, p1 = spr.path(0), spr.path(spr.n - 1)
        if (p1[0] - p0[0]) * dx + (p1[1] - p0[1]) * dy < 0:
            raise SystemExit(f"{spr.name} runs against its path. Bake it 180 degrees around.")
        checked.add(spr.name)

    def stride(spr):
        p0, p1 = spr.path(0), spr.path(spr.n - 1)
        return max(np.hypot(p1[0] - p0[0], p1[1] - p0[1]), 1.0)

    def follow(folder, clips, pts, t0, t1, T):
        """Moves one runner along a polyline at an even speed. Each leg uses its own clip, and the frame follows the distance."""
        legs = [np.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
        d = float(np.clip((T - t0) / (t1 - t0), 0, 1)) * sum(legs)
        done = 0.0
        for k, leg in enumerate(legs):
            if d <= done + leg or k == len(legs) - 1:
                a, b = pts[k], pts[k + 1]
                spr = S(folder, clips[k])
                heading(spr, b[0] - a[0], b[1] - a[1])
                v = min((d - done) / max(leg, 1e-6), 1.0)
                i = int(d / stride(spr) * (spr.n - 1)) % spr.n
                return spr, i, a[0] + (b[0] - a[0]) * v, a[1] + (b[1] - a[1]) * v
            done += leg

    def person(f, spr, i, x, y, pl, grade=None, sh=(6, 2), reveal=1.0, light=None):
        contact_shadow(f, x, y, sh[0], sh[1], 0.8, bayer, ~pl["paper"], 2, occ=pl["occ"])
        spr.draw(f, i, x, y, occ=pl["occ"], grade=grade, bayer=bayer, reveal=reveal, light=light)

    def draw_all(f, people, pl, grade=None, sh=(6, 2), light=None):
        for y, s, i, x, rev in sorted(people, key=lambda p: p[0]):
            person(f, s, i, x, y, pl, grade=grade, sh=sh, reveal=rev, light=light)

    def held(spr, T, t0):
        """Plays the IK ramp once from t0, then rocks gently near the held pose."""
        k = (T - t0) * spr.fps
        if k < 0:
            # Before the gesture the person breathes on the first frames.
            return int(T * spr.fps * 0.5) % 3
        i = int(k) if k < 12 else 12 + int(k * 0.4) % 8
        return int(np.clip(i, 0, spr.n - 1))

    # One full turn of the lamp takes two bars.
    def angle(T):
        return 2 * np.pi * (T - T_HIT) / (8 * 60 / A["tempo"]) - 0.6

    def beam(f, pl, lamp, T, power, reach=320, half=0.14, core=5):
        """Draws a lamp beam that turns in the ground plane. The 30 degree view flattens it to half height."""
        if power <= 0:
            return
        lx, ly = lamp
        a = angle(T)
        dx, dy = X - lx, (Y - ly) * 2.0
        dist = np.hypot(dx, dy) + 1e-6
        off = np.abs(np.angle(np.exp(1j * (np.arctan2(dy, dx) - a))))
        cone = np.clip(1 - off / half, 0, 1) ** 0.5 * np.clip(1 - dist / reach, 0, 1) ** 0.6 * power
        land = ~pl["paper"]
        lit = land & (bayer < cone)
        f[lit] = np.clip(f[lit] * 0.4 + BEAM * 0.7, 0, 255).astype(np.uint8)
        air = pl["paper"] & (bayer < cone * 0.55)
        f[air] = (250, 222, 140)
        glow = (np.hypot(X - lx, Y - ly) + bayer * 3 < core + 2 * power)
        f[glow] = np.clip(f[glow] * 0.3 + BEAM * 0.8, 0, 255).astype(np.uint8)

    def facing(T, lamp, target):
        """How much the beam points at a target, from 0 to 1."""
        d = np.arctan2((target[1] - lamp[1]) * 2.0, target[0] - lamp[0])
        off = abs(np.angle(np.exp(1j * (d - angle(T)))))
        return float(np.clip(1 - off / 0.5, 0, 1))

    def lamp_room(f, power):
        if power <= 0:
            return
        x0, y0, x1, y1 = 251, 72, 277, 92
        part = f[y0:y1, x0:x1].astype(np.float32)
        dark = part.sum(axis=2) < 330
        near = np.clip(1 - np.hypot(X[y0:y1, x0:x1] - LAMP_M[0], (Y[y0:y1, x0:x1] - LAMP_M[1]) * 1.4) / 16, 0.35, 1)
        warm = np.array([255, 214, 120], np.float32) * near[..., None] + part * (1 - near[..., None]) * 0.5
        part[dark] = part[dark] * (1 - power) + warm[dark] * power
        f[y0:y1, x0:x1] = part.astype(np.uint8)

    def window_glow(f, pl, x0, y0, x1, y1, T, on):
        if on <= 0:
            return
        m = np.zeros((G, G), bool)
        m[y0:y1, x0:x1] = True
        m &= (bayer < on * 0.7) & ~pl["paper"]
        f[m] = np.clip(f[m] * 0.6 + np.array([255, 220, 140]) * 0.5, 0, 255).astype(np.uint8)

    # --- The hospital room at night: the keeper gives the boy the key. ---
    def room_key(T):
        pl = P["byoin"]
        f = pl["day"].copy()
        j = S("jiji", "j_give")
        people = [(CHAIR[1], j, held(j, T, 2.2), CHAIR[0], 1.0)]
        if T < 7.4:
            b = S("hero", "b_take")
            people.append((BOY_ROOM[1], b, held(b, T, 3.2), BOY_ROOM[0], min(1.0, T / 0.8)))
        else:
            spr, i, x, y = follow("hero", ["b_out"], [BOY_ROOM, EXIT], 7.4, T_FEST - 0.3, T)
            people.append((y, spr, i, x, min(1.0, (T_FEST - 0.3 - T) / 0.8)))
        # The key glints in the hand that holds it.
        draw_all(f, people, pl, sh=(14, 4))
        hold = "jiji" if T < 4.0 else "hero"
        spr = j if hold == "jiji" else S("hero", "b_take" if T < 7.4 else "b_out")
        if hold == "jiji" or T < 7.4:
            i = held(spr, T, 2.2 if hold == "jiji" else 3.2)
            hx, hy = spr.point(i, "right", CHAIR[0] if hold == "jiji" else BOY_ROOM[0], CHAIR[1] if hold == "jiji" else BOY_ROOM[1])
            if int(T * 4) % 3:
                f[int(hy) - 1:int(hy) + 1, int(hx) - 1:int(hx) + 2] = (250, 220, 120)
        return f

    # --- The festival: the boy runs through the bon-odori ring. ---
    def dancers(T, light_fn=None):
        out = []
        for k, (x, y) in enumerate(ring):
            folder, move = FOLK[k % 4], MOVES[(k * 7 // 4) % 3]
            s = S(folder, move)
            out.append((y, s, s.index(T + k * 0.37, "loop"), x, 1.0))
        return out

    def festival(T, lit=False):
        pl = P["matsuri"]
        f = pl["day"].copy()
        # The lanterns breathe a little.
        warm = (f[..., 0].astype(int) > 200) & (f[..., 1].astype(int) > 150) & ~pl["paper"]
        pulse = (bayer < 0.25 + 0.15 * np.sin(T * 5.0 + X * 0.08)) & warm
        f[pulse] = np.clip(f[pulse] * 1.08, 0, 255).astype(np.uint8)
        people = dancers(T)
        if not lit and T_FEST + 2.6 <= T < T_FEST + 8.8:
            spr, i, x, y = follow("hero", RUN_CLIPS, RUN, T_FEST + 2.6, T_FEST + 8.8, T)
            fade = min(1.0, (T - T_FEST - 2.6) / 0.4, (T_FEST + 8.8 - T) / 0.6)
            people.append((y, spr, i, x, fade))
        if lit:
            beam(f, pl, LAMP_P, T, 1.0, reach=420, core=1)
            hit = facing(T, LAMP_P, RING_C)
            draw_all(f, people, pl, light=(RING_C[0], RING_C[1], 90, (1 + 0.5 * hit, 1 + 0.4 * hit, 1 + 0.2 * hit)) if hit > 0 else None)
        else:
            draw_all(f, people, pl)
        return f

    # --- The cape: the climb, the lamp and the beam. ---
    def cape_night(T):
        pl = P["misaki"]
        f = pl["day"].copy()
        people = []
        if T < T_DOOR:
            spr, i, x, y = follow("hero", STAIR_CLIPS, STAIRS, T_CLIMB, T_DOOR, T)
            people.append((y, spr, i, x, min(1.0, (T_DOOR - T) / 0.35)))
        elif T < T_HIT:
            # He climbs inside the tower. His torch passes each window.
            window_glow(f, pl, 259, 124, 266, 132, T, float(np.clip(1 - abs(T - (T_DOOR + 0.3)) / 0.3, 0, 1)))
            window_glow(f, pl, 259, 101, 266, 110, T, float(np.clip(1 - abs(T - (T_DOOR + 0.75)) / 0.3, 0, 1)))
        else:
            name = "b_pull" if T < T_HIT + 1.6 else "b_wave"
            s = S("hero", name)
            people.append((GALLERY[1], s, s.index(T - T_HIT, "loop" if name == "b_wave" else "clamp"), GALLERY[0], min(1.0, (T - T_HIT + 0.2) / 0.3)))
        if T >= T_HIT + 0.18:
            ign = float(np.clip((T - T_HIT - 0.18) / 0.4, 0, 1))
            # The lamp room fills with light, and the first flash floods the island.
            lamp_room(f, 1.0)
            if T < T_HIT + 0.6:
                flash = (bayer < 0.5 * (1 - (T - T_HIT - 0.18) / 0.42)) & ~pl["paper"]
                f[flash] = np.clip(f[flash] * 0.7 + BEAM * 0.4, 0, 255).astype(np.uint8)
            beam(f, pl, LAMP_M, T, ign)
        draw_all(f, people, pl, sh=(4, 1))
        return f

    def cape_dawn(T):
        u = float(np.clip((T - T_DAWN) / 3.0, 0, 1))
        f = (P["misaki"]["day"] * (1 - u) + P["misaki_asa"]["day"] * u).astype(np.uint8)
        pl = P["misaki_asa"]
        power = float(np.clip((T_OFF - T) / 0.5, 0, 1))
        if power > 0:
            lamp_room(f, power)
            beam(f, pl, LAMP_M, T, power)
        if T < T_EMPTY:
            s = S("hero", "b_sit")
            people = [(CLIFF[1], s, s.index(T, "pingpong"), CLIFF[0], min(1.0, (T - T_DAWN) / 0.6))]
        elif T < T_WALK:
            s = S("hero", "b_key")
            i = held(s, T, T_KEY + 1.0)
            if T > T_WALK - 0.6:
                # He lowers the key before he walks.
                i = max(0, 12 - int((T - T_WALK + 0.6) * s.fps * 1.4))
            people = [(CLIFF[1], s, i, CLIFF[0], 1.0)]
            if T_KEY + 1.6 <= T < T_WALK - 0.6:
                draw_all(f, people, pl, sh=(4, 1))
                hx, hy = s.point(i, "right", CLIFF[0], CLIFF[1])
                if int(T * 3) % 4:
                    f[int(hy) - 1:int(hy) + 1, int(hx):int(hx) + 1] = (255, 226, 140)
                return f
        else:
            # He walks down the stairs to the quay.
            spr, i, x, y = follow("hero", DOWN_CLIPS, DOWN, T_WALK, T_QUAY, T)
            # He walks in under the houses at the quay, out of sight.
            people = [(y, spr, i, x - max(0.0, T - T_QUAY) * 14, float(np.clip((T_QUAY + 0.8 - T) / 0.8, 0, 1)))]
        draw_all(f, people, pl, sh=(4, 1))
        return f

    # --- The hospital room: the keeper watches the beam. At dawn the chair is empty. ---
    def room_watch(T):
        pl = P["byoin"]
        f = pl["day"].copy()
        hit = facing(T, LAMP_W, (LAMP_W[0], LAMP_W[1] + 200))
        view = f.copy()
        beam(view, pl, LAMP_W, T, 1.0, reach=70, core=0)
        win = np.zeros((G, G), bool)
        win[166:212, 150:262] = True
        f[win] = view[win]
        if hit > 0:
            # The beam sweeps across the room through the window.
            sweep = (np.abs(X - (330 - (angle(T) % (2 * np.pi)) / (2 * np.pi) * 360)) < 22) & ~pl["paper"] & (Y > 160) & (bayer < hit * 0.4)
            f[sweep] = np.clip(f[sweep] * 0.8 + BEAM * 0.22, 0, 255).astype(np.uint8)
        j = S("jiji", "j_watch")
        i = held(j, T, T_RAISE) if T >= T_RAISE else int(T * fps * 0.5) % 3
        light = (205, 190, 120, (1 + 0.22 * hit, 1 + 0.17 * hit, 1 + 0.06 * hit)) if hit > 0 else None
        draw_all(f, [(CHAIR[1], j, i, CHAIR[0], 1.0)], pl, sh=(14, 4), light=light)
        return f

    def room_empty(T):
        pl = P["byoin_asa"]
        f = pl["day"].copy()
        # Dust drifts in the dawn light from the open window.
        for k in range(18):
            x = int(150 + (k * 37 + T * (3 + k % 3)) % 120)
            y = int(200 + (k * 23) % 60 + np.sin(T * 0.7 + k) * 6)
            if (k + int(T * 2)) % 4 and not pl["paper"][y, x]:
                f[y, x] = np.clip(f[y, x].astype(int) + 60, 0, 255)
        return f

    title = Image.new("RGB", (240, 50), INK)
    d = ImageDraw.Draw(title)
    d.fontmode = "1"
    big, small = ImageFont.truetype(font_path("msgothic.ttc"), 22), ImageFont.truetype(font_path("msgothic.ttc"), 12)
    d.text((120 - big.getlength(brief["title"]) / 2, 5), brief["title"], font=big, fill=tuple(int(v) for v in paper))
    d.text((120 - small.getlength(brief["title_id"]) / 2, 32), brief["title_id"], font=small, fill=(214, 208, 196))
    title = np.asarray(title)
    state = {"last": None, "scene": None, "at": 0.0}

    def scene_at(T):
        for end, name, fn in ((T_FEST, "key", room_key), (T_CLIMB, "festival", festival), (T_WATCH, "cape", cape_night),
                              (T_DANCE, "watch", room_watch), (T_DAWN, "dance", lambda T: festival(T, lit=True)),
                              (T_EMPTY, "dawn", cape_dawn), (T_KEY, "empty", room_empty)):
            if T < end:
                return name, fn
        return "key_up", cape_dawn

    def draw(i, t, T):
        name, builder = scene_at(T)
        f = builder(T)
        if name != state["scene"]:
            state["scene"], state["at"] = name, T
        u = (T - state["at"]) / 0.2
        if u < 1 and state["last"] is not None:
            hide = bayer > u
            f[hide] = state["last"][hide]
        if 1.0 <= T < 9.0:
            h, w, _ = title.shape
            x0 = (G - w) // 2
            keep = bayer[6:6 + h, x0:x0 + w] < min(1, (T - 1.0) / 0.3, (9.0 - T) / 0.3)
            f[6:6 + h, x0:x0 + w][keep] = title[keep]
        caps.draw(f, T)
        if T < 0.6:
            f[bayer > T / 0.6] = paper
        left = ctx["end"] - T
        if left < 1.2:
            f[bayer > left / 1.2] = paper
        state["last"] = np.array(f, np.uint8)
        return f.astype(np.uint8)

    return draw
