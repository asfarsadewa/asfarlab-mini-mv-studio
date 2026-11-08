# 再走一步: a Hong Kong stair-street. Ah Keung, in his fifties, pushes a loaded hand cart up the steps before dawn, through
# the noon rush and into the afternoon rain. On the steepest flight the cart sticks. The people of the street put their
# hands on it and push, one step on each 再走一步. At night he sits on the roof, and his phone lights up.
# The plates never move. The cart is a Tripo model, baked at the people's camera and scale. See props/bake_cart.py.
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pixkit import INK, Captions, Occlusion, Sprite, bayer_field, contact_shadow
from studio_paths import font_path

STAIRS = [(150, 294), (166, 284), (186, 254), (200, 236), (214, 216), (226, 196), (236, 180)]
CAFE = (147, 294)  # At the edge of the cafe awning, by the foot of the stairs, so he sets off from where he waits.
CART_AT_CAFE = (160, 287)
AUNTIE_SPOT = (85, 296)
DOOR = (125, 292)
ROOF = (230, 258)
HELPERS = {"waitress": (8, 10), "rider": (8, -10), "auntie": (17, 5), "scaffold": (17, -5)}
HELP_FROM = {"waitress": DOOR, "rider": (255, 296), "auntie": AUNTIE_SPOT, "scaffold": (270, 292)}
CROWD = [("clerk", "w_dl", 40.4, 8), ("suit", "w_ur", 41.2, -8), ("city", "w_dl", 42.6, -6), ("clerk", "w_ur", 46.0, 7), ("suit", "w_dl", 47.0, 4)]


def make(ctx):
    G, fps, brief, A, root = ctx["grid"], ctx["fps"], ctx["brief"], ctx["a"], ctx["root"]
    paper = np.array(brief["paper"], np.uint8)
    beats = np.array(A["beats"])
    rng = np.random.default_rng(9)
    bayer = bayer_field(G)
    Y, X = np.mgrid[:G, :G]
    caps = Captions(brief["lines"], paper, top_font=(font_path("simsun.ttc"), 16), low_font=(font_path("msgothic.ttc"), 12))

    def beat(t):
        return float(beats[np.argmin(np.abs(beats - t))])

    T_HIT, T_RAIN, T_PHONE, T_OUT, T_STUCK, T_PUSH, T_CLEAR, T_ROOF, T_LIGHT = (
        brief["hit"], beat(55.6), beat(64.86), beat(77.66), beat(82.2), beat(84.24), beat(94.0), beat(100.6), 104.88)

    def plate(name, occ):
        d = np.asarray(Image.open(root / f"plates/{name}-360.png").convert("RGB")).copy()
        is_paper = (np.abs(d.astype(int) - paper.astype(int)).sum(axis=2) < 24) | (d.astype(int).sum(axis=2) > 720)
        d[is_paper] = paper
        return {"name": name, "day": d, "paper": is_paper, "occ": Occlusion(root, occ)}

    P = {n: plate(n, "jieti") for n in ("jieti", "jieti_wu", "jieti_yu")}
    P["lou"] = plate("lou", "lou")
    sprites = {}

    def S(folder, name):
        if (folder, name) not in sprites:
            sprites[(folder, name)] = Sprite(root, name, folder)
        return sprites[(folder, name)]

    cart_meta = json.loads((root / "props/cart.json").read_text())
    CART = np.asarray(Image.open(root / "props/cart.png").convert("RGBA")).reshape(cart_meta["count"], cart_meta["size"], cart_meta["size"], 4)
    CAX, CAY = cart_meta["anchor"]
    CG = cart_meta["groups"]

    def stamp(f, a, x0, y0):
        h, w = a.shape[:2]
        x0, y0 = int(round(x0)), int(round(y0))
        ax0, ay0, ax1, ay1 = max(x0, 0), max(y0, 0), min(x0 + w, G), min(y0 + h, G)
        if ax0 >= ax1 or ay0 >= ay1:
            return
        part = a[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0]
        solid = part[..., 3] > 0
        f[ay0:ay1, ax0:ax1][solid] = part[..., :3][solid]

    legs = [np.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(STAIRS, STAIRS[1:])]
    TOTAL = sum(legs)

    def on_stairs(d):
        """The point and the direction of travel at distance d along the stairs."""
        d = float(np.clip(d, 0, TOTAL))
        for k, leg in enumerate(legs):
            if d <= leg or k == len(legs) - 1:
                a, b = STAIRS[k], STAIRS[k + 1]
                v = min(d / max(leg, 1e-6), 1.0)
                ux, uy = (b[0] - a[0]) / leg, (b[1] - a[1]) / leg
                return a[0] + (b[0] - a[0]) * v, a[1] + (b[1] - a[1]) * v, ux, uy
            d -= leg

    def stride(spr):
        p0, p1 = spr.path(0), spr.path(spr.n - 1)
        return max(np.hypot(p1[0] - p0[0], p1[1] - p0[1]), 1.0)

    def bursts(T, plan):
        """Distance along the stairs from a plan of (t0, t1, d0, d1) pushes. Between pushes he rests."""
        d = plan[0][2]
        moving = False
        for t0, t1, d0, d1 in plan:
            if T >= t1:
                d = d1
            elif T >= t0:
                d = d0 + (d1 - d0) * (T - t0) / (t1 - t0)
                moving = True
                break
        return d, moving

    # Before dawn he climbs to the middle landing. On each push of the chorus he climbs a little more.
    DAWN_PLAN = [(2.0, 5.5, 0, 14), (7.4, 11.6, 14, 30), (13.6, 18.1, 30, 46), (20.0, 24.4, 46, 58), (26.4, 30.8, 58, 68), (32.8, 37.2, 68, 78),
                 (T_HIT, 42.2, 78, 88), (45.6, 48.6, 88, 98)]
    # In the final chorus the street pushes with him. One push on each 再走一步.
    FINAL_PLAN = [(T_PUSH + 1.6, 87.0, 40, 52), (90.6, 93.4, 52, 66), (96.5, 99.5, 66, TOTAL)]

    def cart_entry(x, y, group, T):
        g0, g1 = CG[group]
        frame = g0 + int(T * (6 if group != "stuck" else 10)) % (g1 - g0)
        return (y, None, frame, x)

    def draw_all(f, items, pl):
        for it in sorted(items, key=lambda p: p[0]):
            y, s, i, x = it[:4]
            if s is None:
                stamp(f, CART[i], x - CAX, y - CAY)
                continue
            contact_shadow(f, x, y, 4, 1, 0.8, bayer, ~pl["paper"], 2, occ=pl["occ"])
            s.draw(f, i, x, y, occ=pl["occ"], bayer=bayer, reveal=it[4] if len(it) > 4 else 1.0, light=it[5] if len(it) > 5 else None)

    def keung_and_cart(T, d, moving, stuck=False):
        cx, cy, ux, uy = on_stairs(d + 12)
        x, y, _, _ = on_stairs(d)
        group = "stuck" if stuck else ("climb" if d > 14 else "roll")
        if moving or stuck:
            spr = S("hero", "k_push")
            i = int((T * 9 if stuck else d / stride(spr) * (spr.n - 1) * 1.0)) % spr.n
        else:
            spr = S("hero", "k_wait")
            i = spr.index(T, "pingpong")
        return [(y, spr, i, x), cart_entry(cx, cy, group if (moving or stuck) else "roll", T if (moving or stuck) else 0)]

    def walker(folder, clip, pts, t0, speed, T):
        segs = [np.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
        dist = float(np.clip((T - t0) * speed, 0, sum(segs)))
        done = 0.0
        for k, seg in enumerate(segs):
            if dist <= done + seg or k == len(segs) - 1:
                a, b = pts[k], pts[k + 1]
                v = min((dist - done) / max(seg, 1e-6), 1.0)
                spr = S(folder, clip if isinstance(clip, str) else clip[k])
                return spr, int(dist / stride(spr) * (spr.n - 1)) % spr.n, a[0] + (b[0] - a[0]) * v, a[1] + (b[1] - a[1]) * v, sum(segs) / speed
            done += seg

    def street_life(T, items, rain=False):
        # The cardboard auntie works the plaza. The waitress stands at her door.
        if T < T_PUSH:
            s = S("auntie", "pick")
            items.append((AUNTIE_SPOT[1], s, s.index(T, "pingpong"), AUNTIE_SPOT[0]))
            if T >= 16.0:
                s = S("waitress", "stand")
                items.append((DOOR[1], s, s.index(T, "pingpong"), DOOR[0], min(1.0, (T - 16.0) / 0.6)))
        if 26.0 <= T < 33.0:
            spr, i, x, y, dur = walker("rider", "w_r", [(60, 298), (275, 296)], 26.0, 32, T)
            items.append((y, spr, i, x, min(1.0, (T - 26.0) / 0.5, (26.0 + dur - T) / 0.5)))

    def crowd(T, items):
        """The noon rush. People pass him on the steps, faster than he climbs."""
        for folder, clip, t0, side in CROWD:
            down = clip == "w_dl"
            pts = [(x + side, y) for x, y in (STAIRS[::-1] if down else STAIRS)]
            if T < t0:
                continue
            spr, i, x, y, dur = walker(folder, clip, pts, t0, 40, T)
            if T < t0 + dur:
                items.append((y, spr, i, x, min(1.0, (T - t0) / 0.4, (t0 + dur - T) / 0.4)))

    drops = [(rng.uniform(20, 340), rng.uniform(30, 330), rng.uniform(0, 1)) for _ in range(160)]

    def rain(f, pl, T, amount):
        for x0, y0, ph in drops[:int(len(drops) * amount)]:
            y = (y0 + (T * 250 + ph * 300)) % 300 + 30
            x = int(x0 - (y - 30) * 0.08) % G
            for k in range(4):
                yy = int(y) + k
                if 0 <= yy < G and not pl["paper"][yy, x]:
                    f[yy, x] = np.clip(f[yy, x].astype(int) + 42, 0, 255)

    def street(T):
        if T < T_HIT:
            pl = P["jieti"]
            f = pl["day"].copy()
        elif T < T_RAIN:
            pl = P["jieti_wu"]
            f = pl["day"].copy()
        else:
            pl = P["jieti_yu"]
            f = pl["day"].copy()
            if T >= T_CLEAR:
                u = float(np.clip((T - T_CLEAR) / 3.0, 0, 1))
                f = np.where((bayer < u)[..., None], P["jieti"]["day"], f).astype(np.uint8)
        items = []
        street_life(T, items)
        if T < T_RAIN:
            d, moving = bursts(T, DAWN_PLAN)
            items += keung_and_cart(T, d, moving)
            if T >= T_HIT:
                crowd(T, items)
        elif T < T_OUT:
            # Rain. He waits under the cafe awning with his cart. His phone stays dark.
            items.append(cart_entry(*CART_AT_CAFE, "roll", 0))
            if T_PHONE <= T < T_PHONE + 6.5:
                s = S("hero", "k_phone")
                k = (T - T_PHONE) * s.fps
                i = min(int(k) if k < 12 else 12 + int(k * 0.3) % 6, s.n - 1)
                items.append((CAFE[1], s, i, CAFE[0]))
            else:
                s = S("hero", "k_wait")
                items.append((CAFE[1], s, s.index(T, "pingpong"), CAFE[0]))
        elif T < T_STUCK:
            # He pushes back out into the rain, to the foot of the stairs and up to the steepest flight.
            u = (T - T_OUT) / (T_STUCK - T_OUT)
            items += keung_and_cart(T, 40 * u, True)
        elif T < T_PUSH + 1.6:
            items += keung_and_cart(T, 40, False, stuck=True)
        else:
            d, moving = bursts(T, FINAL_PLAN)
            items += keung_and_cart(T, d, moving)
        if T >= T_PUSH:
            # One by one, the people of the street come and push.
            cd, climbing = bursts(T, FINAL_PLAN) if T >= T_PUSH + 1.6 else (40, False)
            cx, cy, ux, uy = on_stairs(cd + 12)
            for k, (who, (back, side)) in enumerate(HELPERS.items()):
                slot = (cx - ux * back - uy * side, cy - uy * back + ux * side)
                t0 = T_PUSH + k * 0.5
                start = HELP_FROM[who]
                if T < t0:
                    continue
                arrive = t0 + np.hypot(slot[0] - start[0], slot[1] - start[1]) / 36
                if T < arrive:
                    u = (T - t0) / max(arrive - t0, 1e-6)
                    x, y = start[0] + (slot[0] - start[0]) * u, start[1] + (slot[1] - start[1]) * u
                    clip = "w_ur" if slot[0] >= start[0] else "w_ul"
                    spr = S(who, clip)
                    dist = np.hypot(x - start[0], y - start[1])
                    items.append((y, spr, int(dist / stride(spr) * (spr.n - 1)) % spr.n, x))
                else:
                    # Their steps follow the climb of the cart. Between pushes they hold and breathe.
                    spr = S(who, "help")
                    if climbing:
                        i = int((cd - 40) / stride(spr) * (spr.n - 1) + k * 5) % spr.n
                    else:
                        i = (k * 5 + int(T * 6) % 4) % spr.n
                    items.append((slot[1], spr, i, slot[0]))
        draw_all(f, items, pl)
        if T >= T_RAIN:
            rain(f, pl, T, float(np.clip(1 - (T - T_CLEAR) / 3.0, 0, 1)) if T >= T_CLEAR else 1.0)
        return f

    def roof(T):
        pl = P["lou"]
        f = pl["day"].copy()
        s = S("hero", "k_sit")
        items = [(ROOF[1], s, s.index(T, "pingpong"), ROOF[0])]
        draw_all(f, items, pl)
        if T >= T_LIGHT:
            # The phone in his hand lights up.
            u = float(np.clip((T - T_LIGHT) / 0.4, 0, 1))
            glow = (np.hypot(X - ROOF[0], (Y - (ROOF[1] - 14)) * 1.6) + bayer * 6 < 9 * u) & ~pl["paper"]
            f[glow] = np.clip(f[glow].astype(np.float32) * 1.35 + 20, 0, 255).astype(np.uint8)
            f[ROOF[1] - 15:ROOF[1] - 13, ROOF[0] - 1:ROOF[0] + 2] = (214, 236, 255)
        return f

    CLOSE = plate("shouji", "lou")["day"]
    T_CLOSE = 104.0
    # The glass of the phone is a tilted four-sided shape on the close-up plate.
    mask = Image.new("L", (G, G), 0)
    ImageDraw.Draw(mask).polygon([(205, 107), (246, 113), (239, 154), (198, 149)], fill=255)
    screen = np.asarray(mask) > 0
    caller = Image.new("L", (40, 20), 0)
    dc = ImageDraw.Draw(caller)
    dc.fontmode = "1"
    dc.text((4, 1), "女儿", font=ImageFont.truetype(font_path("simsun.ttc"), 16), fill=255)
    caller = np.asarray(caller) > 0

    def close_up(T):
        """The phone in his hand. It lights up, and it shows who is calling."""
        f = CLOSE.copy()
        if T >= T_LIGHT:
            u = float(np.clip((T - T_LIGHT) / 0.3, 0, 1))
            lit = screen & (bayer < u)
            f[lit] = (196, 226, 250)
            if u >= 1:
                ys, xs = np.nonzero(caller)
                f[ys + 121, xs + 202] = (24, 34, 56)
            # The phone buzzes for a moment.
            if T < T_LIGHT + 1.2 and int(T * 20) % 2:
                f = np.roll(f, 1, axis=1)
        return f

    title = Image.new("RGB", (240, 50), INK)
    d = ImageDraw.Draw(title)
    d.fontmode = "1"
    big, small = ImageFont.truetype(font_path("simsun.ttc"), 22), ImageFont.truetype(font_path("msgothic.ttc"), 12)
    d.text((120 - big.getlength(brief["title"]) / 2, 4), brief["title"], font=big, fill=tuple(int(v) for v in paper))
    d.text((120 - small.getlength(brief["title_id"]) / 2, 33), brief["title_id"], font=small, fill=(214, 208, 196))
    title = np.asarray(title)
    state = {"last": None, "scene": None, "at": 0.0}

    def scene_name(T):
        if T >= T_CLOSE:
            return "close"
        if T >= T_ROOF:
            return "roof"
        return "dawn" if T < T_HIT else ("noon" if T < T_RAIN else "rain")

    def draw(i, t, T):
        name = scene_name(T)
        f = close_up(T) if name == "close" else (roof(T) if name == "roof" else street(T))
        if name != state["scene"]:
            state["scene"], state["at"] = name, T
        u = (T - state["at"]) / 0.3
        if u < 1 and state["last"] is not None:
            hide = bayer > u
            f[hide] = state["last"][hide]
        if 0.8 <= T < 6.6:
            h, w, _ = title.shape
            x0 = (G - w) // 2
            keep = bayer[6:6 + h, x0:x0 + w] < min(1, (T - 0.8) / 0.3, (6.6 - T) / 0.3)
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
