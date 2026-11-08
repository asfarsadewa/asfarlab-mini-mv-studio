# 照常营业: a night-market noodle stall. Her father died, and the funeral was this morning. That evening she rolls up
# the shutter anyway, ties on his apron and cooks for the night-shift regulars. In the rain nobody leaves. When the last
# table goes, she sits and cries. The next evening the shutter goes up again, the queue is longer, and she hangs the sign.
# The plates never move. Footprints guard every path. Every walker faces the way that it moves.
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pixkit import INK, Captions, Occlusion, Sprite, bayer_field, contact_shadow, small_flame
from studio_paths import font_path

SHUTTER = (142, 258)
COUNTER = (138, 236)  # Her hips sit at the counter top, so the counter hides her legs.
HOOK = COUNTER  # The apron hangs on the back wall behind the counter. She turns round to take it.
APRON = (141, 200)
CORNER_IN = (170, 250)
BEHIND = (157, 238)
STOOL = (131, 270)
ENTRY = (300, 276)
SEATS = {"clerk": ((103, 270), "c_eat_r"), "wang": ((131, 270), "c_eat_l"), "nurse": ((192, 272), "c_eat_r"),
         "builder": ((220, 272), "c_eat_l"), "driver": ((161, 252), "c_eat_r")}
BOWLS = {"clerk": (110, 251), "wang": (126, 251), "nurse": (200, 249), "builder": (214, 249), "driver": (170, 233)}
ARRIVE = {"clerk": 40.2, "wang": 41.6, "nurse": 43.0, "builder": 44.4, "driver": 45.8}
LEAVE = {"driver": 73.9, "clerk": 74.4, "builder": 75.0, "nurse": 75.4}
QUEUE = {"clerk": (234, 246), "builder": (248, 253), "driver": (262, 260), "auntie": (276, 267)}
FINAL_SEATS = {"wang": 81.4, "nurse": 82.4}
WOK, POT = (153, 226), (126, 219)
STEAM = (238, 234, 226)


def make(ctx):
    G, fps, brief, A, root = ctx["grid"], ctx["fps"], ctx["brief"], ctx["a"], ctx["root"]
    paper = np.array(brief["paper"], np.uint8)
    beats = np.array(A["beats"])
    rng = np.random.default_rng(3)
    bayer = bayer_field(G)
    Y, X = np.mgrid[:G, :G]
    caps = Captions(brief["lines"], paper, top_font=(font_path("simsun.ttc"), 16), low_font=(font_path("msgothic.ttc"), 12))
    shapes = json.loads((root / "occluders.json").read_text(encoding="utf-8"))

    def beat(t):
        return float(beats[np.argmin(np.abs(beats - t))])

    T_LIFT, T_IN, T_FIRE, T_TO_HOOK, T_HOOK, T_TIE, T_BACK, T_BURN, T_HIT, T_WIPE1, T_RAIN, T_PAY, T_SIT, T_NEXT, T_SIGN = (
        beat(7.1), beat(11.9), beat(13.5), beat(19.4), beat(20.6), beat(26.9), beat(32.0), beat(34.4), brief["hit"], beat(53.1),
        beat(63.5), beat(70.4), beat(77.2), beat(80.56), beat(106.86))
    T_DIM = 73.9

    def plate(name):
        d = np.asarray(Image.open(root / f"plates/{name}-360.png").convert("RGB")).copy()
        is_paper = (np.abs(d.astype(int) - paper.astype(int)).sum(axis=2) < 24) | (d.astype(int).sum(axis=2) > 720)
        d[is_paper] = paper
        return {"name": name, "day": d, "paper": is_paper, "occ": Occlusion(root, "yeshi_guan" if name == "yeshi_guan" else "yeshi")}

    P = {n: plate(n) for n in ("yeshi", "yeshi_guan", "yeshi_yu")}
    sprites = {}

    def S(folder, name):
        if (folder, name) not in sprites:
            sprites[(folder, name)] = Sprite(root, name, folder)
        return sprites[(folder, name)]

    def clearance(x, y, name="yeshi"):
        solids = [o["footprint"] for o in shapes[name] if "footprint" in o]
        return min(np.hypot((x - cx) / rx, (y - cy) / ry) for cx, cy, rx, ry in solids)

    def path_points(pts, step=3):
        out = []
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = max(int(np.hypot(x1 - x0, y1 - y0) / step), 1)
            out += [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n + 1)]
        return out

    def entry_path(c, seat):
        return [ENTRY, (seat[0] + 6, 277), seat]

    def exit_path(c, seat):
        return entry_path(c, seat)[::-1]

    ARRIVAL = [(246, 214), (236, 277), (150, 273), SHUTTER]  # In front of the stacked stools on the dusk plate.

    def queue_path(spot):
        return [ENTRY, (spot[0] + 14, spot[1] + 8), spot]

    TO_COUNTER = [SHUTTER, CORNER_IN, BEHIND, COUNTER]
    TO_STOOL = [COUNTER, BEHIND, CORNER_IN, (150, 268), STOOL]
    TO_SIGN = [COUNTER, BEHIND, CORNER_IN, SHUTTER]
    walks = [TO_COUNTER, TO_STOOL, TO_SIGN, ARRIVAL]
    walks += [entry_path(c, SEATS[c][0]) for c in SEATS] + [queue_path(q) for q in QUEUE.values()]
    walks += [exit_path(c, SEATS[c][0]) for c in SEATS]
    low = min(clearance(x, y) for w in walks for x, y in path_points(w))
    print("Footprint clearance on yeshi, with 1.0 at the object edge:", round(float(low), 2), flush=True)
    dusk = min(clearance(x, y, "yeshi_guan") for x, y in path_points(ARRIVAL))
    print("Footprint clearance on yeshi_guan, with 1.0 at the object edge:", round(float(dusk), 2), flush=True)
    if min(low, dusk) < 1.0:
        raise SystemExit(f"A person walks inside a solid object: {min(low, dusk):.2f}")
    checked = set()

    def heading(spr, dx, dy):
        """Stops the render if a clip walks against its path. A backward walker reads as a moonwalk."""
        if spr.name in checked or np.hypot(dx, dy) < 8:
            return
        p0, p1 = spr.path(0), spr.path(spr.n - 1)
        if (p1[0] - p0[0]) * dx + (p1[1] - p0[1]) * dy < 0:
            raise SystemExit(f"{spr.name} walks against its path. Bake it 180 degrees around.")
        checked.add(spr.name)

    def stride(spr):
        p0, p1 = spr.path(0), spr.path(spr.n - 1)
        return max(np.hypot(p1[0] - p0[0], p1[1] - p0[1]), 1.0)

    def pick_clip(folder, dx, dy):
        """Chooses the walk clip that faces the way of one leg."""
        hero = folder == "hero"
        if dx < 0 and dy < -0.5 * abs(dx) and not hero:
            return "c_walk_ul"
        if dx < 0 and dy > 0.5 * abs(dx) and hero:
            return "h_walk_dl"
        if dx >= 0:
            return "h_walk_r" if hero else "c_walk_r"
        return "h_walk_l" if hero else "c_walk_l"

    def follow(folder, pts, t0, speed, T):
        """Walks one person along a polyline at a steady speed in grid pixels per second."""
        legs = [np.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
        d = float(np.clip((T - t0) * speed, 0, sum(legs)))
        done = 0.0
        for k, leg in enumerate(legs):
            if d <= done + leg or k == len(legs) - 1:
                a, b = pts[k], pts[k + 1]
                spr = S(folder, pick_clip(folder, b[0] - a[0], b[1] - a[1]))
                heading(spr, b[0] - a[0], b[1] - a[1])
                v = min((d - done) / max(leg, 1e-6), 1.0)
                return spr, int(d / stride(spr) * (spr.n - 1)) % spr.n, a[0] + (b[0] - a[0]) * v, a[1] + (b[1] - a[1]) * v
            done += leg

    def walk_time(pts, speed):
        return sum(np.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])) / speed

    def act(folder, clip, T, t0, x, y, mode="loop"):
        spr = S(folder, clip)
        period = (spr.n if mode == "loop" else 2 * (spr.n - 1)) / spr.fps
        return (y, spr, spr.index((T - t0) % period, mode), x)

    def stretch(folder, clip, T, t0, t1, x, y):
        """Plays a clip once, stretched to fill t0 to t1, so its last frame never holds."""
        spr = S(folder, clip)
        u = float(np.clip((T - t0) / (t1 - t0), 0, 1))
        return (y, spr, int(u * (spr.n - 1)), x)

    def held(folder, clip, T, t0, x, y):
        """Plays an IK ramp once from t0, then rocks gently near the held pose."""
        spr = S(folder, clip)
        k = (T - t0) * spr.fps
        i = int(T * spr.fps * 0.5) % 3 if k < 0 else (int(k) if k < 12 else 12 + int(k * 0.4) % 8)
        return (y, spr, min(i, spr.n - 1), x)

    def person(f, spr, i, x, y, pl, reveal=1.0, light=None):
        contact_shadow(f, x, y, 6, 2, 0.8, bayer, ~pl["paper"], 2, occ=pl["occ"])
        spr.draw(f, i, x, y, occ=pl["occ"], bayer=bayer, reveal=reveal, light=light)

    def draw_all(f, people, pl, light=None):
        for p in sorted(people, key=lambda p: p[0]):
            y, s, i, x = p[:4]
            person(f, s, i, x, y, pl, reveal=p[4] if len(p) > 4 else 1.0, light=light)

    def puff(f, cx, cy, r, a, col=STEAM):
        x0, y0, x1, y1 = max(int(cx - r), 0), max(int(cy - r), 0), min(int(cx + r) + 1, G), min(int(cy + r) + 1, G)
        if x0 >= x1 or y0 >= y1:
            return
        yy, xx = np.mgrid[y0:y1, x0:x1]
        m = (np.hypot(xx - cx, yy - cy) <= r) & (bayer[y0:y1, x0:x1] < a)
        f[y0:y1, x0:x1][m] = col

    def steam(f, x, y, T, k0=0, col=STEAM, strength=0.5):
        for k in range(4):
            age = ((T * 0.6 + k / 4 + k0 * 0.13) % 1.0)
            puff(f, x + np.sin(T * 1.7 + k * 2 + k0) * 2, y - age * 18, 1.2 + age * 2.5, strength * (1 - age), col)

    def bowl(f, x, y, T, k):
        f[y, x - 2:x + 3] = (236, 232, 222)
        f[y + 1, x - 1:x + 2] = (200, 196, 188)
        steam(f, x, y - 1, T, k, strength=0.35)

    def stove(f, T, on):
        if on:
            small_flame(f, WOK[0], WOK[1] + 8, T, 3)
            steam(f, WOK[0], WOK[1] - 2, T, 1)
            steam(f, POT[0], POT[1] - 4, T, 2)

    def apron(f):
        x, y = APRON
        f[y:y + 8, x - 2:x + 3] = (52, 62, 96)
        f[y, x - 3:x + 4] = (40, 46, 70)

    rain_drops = [(rng.uniform(20, 340), rng.uniform(40, 330), rng.uniform(0, 1)) for _ in range(150)]

    def rain(f, pl, T):
        for x0, y0, ph in rain_drops:
            y = (y0 + (T * 240 + ph * 300)) % 290 + 40
            x = int(x0 - (y - 40) * 0.1) % G
            for d in range(4):
                yy, xx = int(y) + d, x
                if 0 <= yy < G and not pl["paper"][yy, xx]:
                    f[yy, xx] = np.clip(f[yy, xx].astype(int) + 40, 0, 255)

    # The red paper sign that she hangs at the end.
    sign = Image.new("RGB", (12, 46), (178, 34, 28))
    ds = ImageDraw.Draw(sign)
    ds.fontmode = "1"
    sf = ImageFont.truetype(font_path("simsun.ttc"), 10)
    for k, ch in enumerate("照常营业"):
        ds.text((1, 1 + k * 11), ch, font=sf, fill=(250, 220, 120))
    SIGN = np.asarray(sign)

    def customers_first_night(T, pl):
        people = []
        for c, (seat, eat) in SEATS.items():
            t0 = ARRIVE[c]
            pts = entry_path(c, seat)
            t_sit = t0 + walk_time(pts, 32)
            t_out = LEAVE.get(c)
            if T < t0:
                continue
            if T < t_sit:
                spr, i, x, y = follow(c, pts, t0, 32, T)
                people.append((y, spr, i, x, min(1.0, (T - t0) / 0.6)))
                continue
            if c == "wang" and T >= T_PAY:
                if T < T_PAY + 1.6:
                    people.append(act(c, "c_offer", T, T_PAY, *seat))
                elif T < T_PAY + 2.8:
                    people.append(act(c, "c_nod", T, T_PAY + 1.6, *seat))
                else:
                    back = exit_path(c, seat)
                    if T < T_PAY + 2.8 + walk_time(back, 32):
                        spr, i, x, y = follow(c, back, T_PAY + 2.8, 32, T)
                        people.append((y, spr, i, x, min(1.0, (T_PAY + 2.8 + walk_time(back, 32) - T) / 0.8)))
                continue
            if t_out and T >= t_out:
                back = exit_path(c, seat)
                if T < t_out + walk_time(back, 32):
                    spr, i, x, y = follow(c, back, t_out, 32, T)
                    people.append((y, spr, i, x, min(1.0, (t_out + walk_time(back, 32) - T) / 0.8)))
                continue
            people.append(act(c, eat, T, t_sit + list(SEATS).index(c) * 0.3, *seat))
        return people

    def bowls_first_night(f, T):
        for k, c in enumerate(SEATS):
            t_served = ARRIVE[c] + walk_time(entry_path(c, SEATS[c][0]), 32) + 1.2
            gone = T_PAY + 2.0 if c == "wang" else LEAVE.get(c, 999)
            if t_served <= T < gone:
                bowl(f, *BOWLS[c], T, k)
        if T_PAY + 1.2 <= T < T_SIT:
            f[249:251, 122:125] = (232, 196, 70)  # The coins that Old Wang leaves.

    def night(T):
        rainy = T >= T_RAIN
        if T < T_RAIN + 0.6 and rainy:
            u = (T - T_RAIN) / 0.6
            f = np.where((bayer < u)[..., None], P["yeshi_yu"]["day"], P["yeshi"]["day"]).astype(np.uint8)
        else:
            f = P["yeshi_yu" if rainy else "yeshi"]["day"].copy()
        pl = P["yeshi_guan"] if T < T_LIFT + 2.0 else P["yeshi"]
        if T < T_LIFT + 4.0:
            # The shutter rolls up as she lifts it. The lit stall shows from the bottom up.
            u = float(np.clip((T - T_LIFT - 1.0) / 2.2, 0, 1))
            line = 248 - 58 * u
            shut = (X >= 82) & (X <= 205) & (Y >= 190) & (Y <= 248)
            show = np.where(shut, Y > line, bayer < u)
            f = np.where(show[..., None], f, P["yeshi_guan"]["day"]).astype(np.uint8)
        if T_LIFT + 3.2 <= T < T_HOOK + 1.2:
            apron(f)
        stove(f, T, T_FIRE + 0.8 <= T < T_DIM + 2.0)
        if T_BURN <= T < T_BURN + 2.6:
            u = T - T_BURN
            for k in range(5):
                puff(f, WOK[0] + np.sin(k + u) * 2, WOK[1] - 3 - k * 5 - u * 6, 2 + k * 0.6 + u, max(0.0, 0.6 - u * 0.2), (70, 64, 60))
        bowls_first_night(f, T)
        people = customers_first_night(T, pl)
        # Her own path through the night.
        if T < 1.0:
            pass  # She has not come round the corner yet.
        elif T < T_LIFT:
            # The walk fills the time to the lift exactly, so she never stands still.
            speed = walk_time(ARRIVAL, 1.0) / (T_LIFT - 1.0)
            spr, i, x, y = follow("hero", ARRIVAL, 1.0, speed, T)
            people.append((y, spr, i, x, min(1.0, (T - 1.0) / 0.6)))
        elif T_LIFT <= T < T_IN:
            people.append(stretch("hero", "h_lift", T, T_LIFT, T_IN, *SHUTTER))
        elif T < T_IN + walk_time(TO_COUNTER, 30):
            spr, i, x, y = follow("hero", TO_COUNTER, T_IN, 30, T)
            people.append((y, spr, i, x))
        elif T < T_HOOK:
            # She lights the stove. Her hands shake.
            spr = S("hero", "h_cook")
            i = int((T - T_IN) * spr.fps * 0.5) % spr.n
            people.append((COUNTER[1], spr, i, COUNTER[0] + (1 if int(T * 9) % 2 else 0)))
        elif T < T_TIE:
            people.append(held("hero", "h_hook", T, T_HOOK + 1.0, *HOOK))
        elif T < T_BACK:
            people.append(held("hero", "h_tie", T, T_TIE, *HOOK))
        elif T_BURN + 0.8 <= T < T_BURN + 2.4 or T_WIPE1 <= T < T_WIPE1 + 2.6:
            # She turns away and wipes her eyes, then turns back to the pot.
            people.append(held("hero", "h_wipe", T, T_BURN + 0.8 if T < T_HIT else T_WIPE1, *COUNTER))
        elif T < T_DIM:
            people.append(act("hero", "h_cook", T, T_BACK, *COUNTER))
        elif T < T_DIM + walk_time(TO_STOOL, 30):
            # The last table goes. She walks out and sits on a stool.
            spr, i, x, y = follow("hero", TO_STOOL, T_DIM, 30, T)
            people.append((y, spr, i, x))
        else:
            people.append(held("hero", "h_cry", T, T_SIT + 0.6, *STOOL))
        draw_all(f, people, pl)
        if rainy:
            rain(f, pl, T)
        if T >= T_DIM:
            # Three in the morning. The bulbs go out one by one.
            u = float(np.clip((T - T_DIM) / 3.0, 0, 1))
            dark = ~pl["paper"]
            f[dark] = (f[dark] * (1 - 0.3 * u)).astype(np.uint8)
        return f

    def next_evening(T):
        u = float(np.clip((T - T_NEXT - 1.0) / 2.2, 0, 1))
        f = P["yeshi"]["day"].copy()
        line = 248 - 58 * u
        shut = (X >= 82) & (X <= 205) & (Y >= 190) & (Y <= 248)
        show = np.where(shut, Y > line, bayer < u)
        f = np.where(show[..., None], f, P["yeshi_guan"]["day"]).astype(np.uint8)
        pl = P["yeshi"]
        t_lit = T_NEXT + 4.0 + walk_time(TO_COUNTER, 30)
        stove(f, T, T >= t_lit)
        people = []
        for k, (c, t0) in enumerate(FINAL_SEATS.items()):
            seat, eat = SEATS[c]
            pts = entry_path(c, seat)
            t_sit = t0 + walk_time(pts, 32)
            if T < t0:
                continue
            if T < t_sit:
                spr, i, x, y = follow(c, pts, t0, 32, T)
                people.append((y, spr, i, x, min(1.0, (T - t0) / 0.6)))
            else:
                people.append(act(c, eat, T, t_sit, *seat))
                if T >= t_sit + 1.5:
                    bowl(f, *BOWLS[c], T, k)
        for k, (c, spot) in enumerate(QUEUE.items()):
            t0 = T_NEXT + 3.0 + k * 1.3
            pts = queue_path(spot)
            if T < t0:
                continue
            if T < t0 + walk_time(pts, 32):
                spr, i, x, y = follow(c, pts, t0, 32, T)
                people.append((y, spr, i, x, min(1.0, (T - t0) / 0.6)))
            else:
                people.append(act(c, "c_queue", T, t0 + k * 0.4, *spot, mode="pingpong"))
        t_to_sign = T_SIGN - walk_time(TO_SIGN, 30)
        if T < T_NEXT + 4.0:
            people.append(stretch("hero", "h_lift", T, T_NEXT, T_NEXT + 4.0, *SHUTTER))
        elif T < t_lit:
            spr, i, x, y = follow("hero", TO_COUNTER, T_NEXT + 4.0, 30, T)
            people.append((y, spr, i, x))
        elif T < t_to_sign:
            people.append(act("hero", "h_cook", T, t_lit, *COUNTER))
        elif T < T_SIGN:
            spr, i, x, y = follow("hero", TO_SIGN, t_to_sign, 30, T)
            people.append((y, spr, i, x))
        else:
            people.append(held("hero", "h_hang", T, T_SIGN, *SHUTTER))
        if T >= T_SIGN + 0.8:
            h, w, _ = SIGN.shape
            f[196:196 + h, SHUTTER[0] - w // 2:SHUTTER[0] - w // 2 + w] = SIGN
        draw_all(f, people, pl)
        return f

    title = Image.new("RGB", (240, 50), INK)
    d = ImageDraw.Draw(title)
    d.fontmode = "1"
    big, small = ImageFont.truetype(font_path("simsun.ttc"), 22), ImageFont.truetype(font_path("msgothic.ttc"), 12)
    d.text((120 - big.getlength(brief["title"]) / 2, 4), brief["title"], font=big, fill=tuple(int(v) for v in paper))
    d.text((120 - small.getlength(brief["title_id"]) / 2, 33), brief["title_id"], font=small, fill=(214, 208, 196))
    title = np.asarray(title)
    state = {"last": None, "scene": None, "at": 0.0}

    def draw(i, t, T):
        name, builder = ("night", night) if T < T_NEXT else ("next", next_evening)
        f = builder(T)
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
