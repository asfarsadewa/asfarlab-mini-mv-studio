# 独上高处: an instrumental. A martial artist climbs a sacred mountain level by level. At the foot a crowd trains as one.
# Higher up he duels fewer rivals, and each bows and leaves. Near the top his last rival is an old friend, and he turns
# away from the final strike. At the summit he moves alone under the moon. A poem appears in vertical columns, one
# character on each beat, read right to left. The Indonesian line is the only subtitle.
# The plates never move, and each island is smaller than the last.
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
from pixkit import INK, Captions, Occlusion, Sprite, bayer_field, contact_shadow
from studio_paths import font_path

INK_POEM = np.array([38, 30, 34], np.uint8)
SEAL = np.array([178, 34, 30], np.uint8)
ROWS = [(150, 236), (178, 236), (206, 236), (234, 236), (150, 250), (178, 250), (234, 250), (150, 264), (178, 264), (234, 264), (262, 250), (262, 264)]
HERO_ROW = (206, 264)
GATE = (210, 224)
PLAT_HERO, PLAT_RIVAL = (185, 228), (222, 212)
LEDGE_HERO, LEDGE_FRIEND = (165, 198), (225, 195)
PEAK = (205, 192)


def make(ctx):
    G, fps, brief, A, root = ctx["grid"], ctx["fps"], ctx["brief"], ctx["a"], ctx["root"]
    paper = np.array(brief["paper"], np.uint8)
    beats = np.array(A["beats"])
    BEAT = float(np.median(np.diff(beats)))
    rng = np.random.default_rng(21)
    bayer = bayer_field(G)
    Y, X = np.mgrid[:G, :G]
    caps = Captions(brief["lines"], paper, top_font=(font_path("msgothic.ttc"), 13), low_font=(font_path("msgothic.ttc"), 12))
    poem = brief["poem"]

    def beat(t):
        return float(beats[np.argmin(np.abs(beats - t))])

    T_LEAVE, T_PLAT, T_DUEL1, T_BOW1, T_GO1, T_RIVAL2, T_DUEL2, T_BOW2, T_LEDGE, T_FORM, T_FRIEND, T_FIGHT, T_TURN, T_PAST, T_PEAK, T_STILL = (
        beat(12.27), beat(23.77), beat(27.5), beat(33.5), beat(35.1), beat(37.0), beat(40.2), beat(45.0), beat(46.87), beat(53.0),
        beat(60.4), beat(70.6), beat(77.5), beat(79.2), beat(81.03), beat(104.0))

    def plate(name):
        d = np.asarray(Image.open(root / f"plates/{name}-360.png").convert("RGB")).copy()
        # Pale pixels count as paper only where they connect to the frame edge. Snow inside the island stays snow.
        pale = (np.abs(d.astype(int) - paper.astype(int)).sum(axis=2) < 24) | (d.astype(int).sum(axis=2) > 720)
        lab, _ = ndimage.label(pale)
        edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
        is_paper = np.isin(lab, edge[edge > 0])
        d[is_paper] = paper
        return {"name": name, "day": d, "paper": is_paper, "occ": Occlusion(root, name)}

    P = {n: plate(n) for n in ("shanmen", "shanlu", "xuanya", "dingfeng")}
    # The summit is night: the island darkens to a cold blue.
    night = P["dingfeng"]["day"].astype(np.float32)
    land = ~P["dingfeng"]["paper"]
    night[land] = night[land] * np.array([0.55, 0.6, 0.85])
    P["dingfeng"]["day"] = night.astype(np.uint8)
    sprites = {}

    def S(folder, name):
        if (folder, name) not in sprites:
            sprites[(folder, name)] = Sprite(root, name, folder)
        return sprites[(folder, name)]

    def stride(spr):
        p0, p1 = spr.path(0), spr.path(spr.n - 1)
        return max(np.hypot(p1[0] - p0[0], p1[1] - p0[1]), 1.0)

    def walk(folder, clip, pts, t0, t1, T):
        segs = [np.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
        d = float(np.clip((T - t0) / (t1 - t0), 0, 1)) * sum(segs)
        done = 0.0
        for k, seg in enumerate(segs):
            if d <= done + seg or k == len(segs) - 1:
                a, b = pts[k], pts[k + 1]
                v = min((d - done) / max(seg, 1e-6), 1.0)
                spr = S(folder, clip)
                return (a[1] + (b[1] - a[1]) * v, spr, int(d / stride(spr) * (spr.n - 1)) % spr.n, a[0] + (b[0] - a[0]) * v)
            done += seg

    def act(folder, clip, T, t0, pos, mode="loop"):
        spr = S(folder, clip)
        if mode == "once":
            return (pos[1], spr, min(int(max(T - t0, 0) * spr.fps), spr.n - 1), pos[0])
        period = (spr.n if mode == "loop" else 2 * (spr.n - 1)) / spr.fps
        return (pos[1], spr, spr.index((T - t0) % period, mode), pos[0])

    def draw_all(f, items, pl, light=None):
        for it in sorted(items, key=lambda p: p[0]):
            y, s, i, x = it[:4]
            contact_shadow(f, x, y, 4, 1, 0.8, bayer, ~pl["paper"], 2, occ=pl["occ"])
            s.draw(f, i, x, y, occ=pl["occ"], bayer=bayer, reveal=it[4] if len(it) > 4 else 1.0, light=light)

    # A duel is a list of exchanges, two beats each. In each exchange one strikes and the other blocks.
    EXCHANGES = [("h_kick_f", "r_block"), ("h_block", "r_kick_r"), ("h_kick_spin", "r_block"), ("h_block", "r_kick_f"), ("h_kick_r", "r_block"), ("h_block", "r_kick_r")]

    def duel(T, t0, t1, rival, hero_pos, rival_pos, offset=0):
        k = int((T - t0) / (2 * BEAT))
        if T >= t1:
            return [act("hero", "h_stance", T, t1, hero_pos, "pingpong"), act(rival, "r_stance", T, t1, rival_pos, "pingpong")]
        hc, rc = EXCHANGES[(k + offset) % len(EXCHANGES)]
        ts = t0 + k * 2 * BEAT
        return [act("hero", hc, T, ts, hero_pos, "once"), act(rival, rc, T, ts, rival_pos, "once")]

    flakes = [(rng.uniform(0, 360), rng.uniform(0, 360), rng.uniform(0.5, 1.5)) for _ in range(90)]

    def snow(f, pl, T, amount, col=(244, 246, 252)):
        for x0, y0, v in flakes[:int(len(flakes) * amount)]:
            y = (y0 + T * 12 * v) % 300 + 40
            x = int(x0 + np.sin(T * 0.8 * v + y0) * 6) % G
            if not pl["paper"][int(y), x]:
                f[int(y), x] = col

    # --- The courtyard: the crowd trains as one. He steps out and leaves through the gate. ---
    def courtyard(T):
        pl = P["shanmen"]
        f = pl["day"].copy()
        items = []
        for k, pos in enumerate(ROWS):
            items.append(act(f"t{k % 3 + 1}", "form", T, 0.4 + (k % 3) * 0.06, pos))
        if T < T_LEAVE:
            items.append(act("hero", "h_form", T, 0.4, HERO_ROW))
        elif T < T_LEAVE + 1.0:
            items.append(act("hero", "h_stand", T, T_LEAVE, HERO_ROW, "pingpong"))
        elif T < T_LEAVE + 6.0:
            it = walk("hero", "h_walk_ur", [HERO_ROW, (214, 240), GATE], T_LEAVE + 1.0, T_LEAVE + 6.0, T)
            items.append(it + (min(1.0, (T_LEAVE + 6.0 - T) / 0.8),))
        draw_all(f, items, pl)
        return f

    # --- The platform: two duels. Each rival bows and leaves up the path. ---
    def platform(T):
        pl = P["shanlu"]
        f = pl["day"].copy()
        items = []
        if T < T_DUEL1:
            it = walk("hero", "h_walk_ur", [(150, 258), PLAT_HERO], T_PLAT, T_DUEL1, T)
            items.append(it + (min(1.0, (T - T_PLAT) / 0.6),))
            items.append(act("rong", "r_stance", T, T_PLAT, PLAT_RIVAL, "pingpong"))
        elif T < T_BOW1:
            items += duel(T, T_DUEL1, T_BOW1, "rong", PLAT_HERO, PLAT_RIVAL)
        elif T < T_GO1:
            items += [act("hero", "h_salute", T, T_BOW1, PLAT_HERO, "once"), act("rong", "r_salute", T, T_BOW1, PLAT_RIVAL, "once")]
        else:
            items.append(act("hero", "h_stance", T, T_GO1, PLAT_HERO, "pingpong") if T < T_DUEL2 else None)
            if T < T_GO1 + 3.2:
                it = walk("rong", "r_walk_ur", [PLAT_RIVAL, (248, 192), (266, 168)], T_GO1, T_GO1 + 3.2, T)
                items.append(it + (min(1.0, (T_GO1 + 3.2 - T) / 0.8),))
            if T_RIVAL2 <= T < T_DUEL2:
                # The next rival comes down the path from above.
                it = walk("carver", "r_walk_dl", [(266, 168), (248, 192), PLAT_RIVAL], T_RIVAL2, T_DUEL2, T)
                items.append(it + (min(1.0, (T - T_RIVAL2) / 0.8),))
            elif T_DUEL2 <= T < T_BOW2:
                items += duel(T, T_DUEL2, T_BOW2, "carver", PLAT_HERO, PLAT_RIVAL, offset=2)
            elif T >= T_BOW2:
                items += [act("hero", "h_salute", T, T_BOW2, PLAT_HERO, "once"), act("carver", "r_salute", T, T_BOW2, PLAT_RIVAL, "once")]
        draw_all(f, [i for i in items if i is not None], pl)
        return f

    # --- The ledge: alone, then the old friend. He turns away from the last strike. ---
    def ledge(T):
        pl = P["xuanya"]
        f = pl["day"].copy()
        items = []
        if T < T_FORM:
            it = walk("hero", "h_walk_r", [(132, 202), LEDGE_HERO], T_LEDGE, T_FORM, T)
            items.append(it + (min(1.0, (T - T_LEDGE) / 0.6),))
        elif T < T_FIGHT:
            items.append(act("hero", "h_form" if T < T_FRIEND + 2.0 else "h_stance", T, T_FORM, LEDGE_HERO, "loop" if T < T_FRIEND + 2.0 else "pingpong"))
        if T_FRIEND <= T < T_FRIEND + 4.0:
            # The old friend comes down the steps from the peak as the snow begins.
            it = walk("friend", "r_walk_dl", [(290, 158), (268, 180), LEDGE_FRIEND], T_FRIEND, T_FRIEND + 4.0, T)
            items.append(it + (min(1.0, (T - T_FRIEND) / 0.8),))
        elif T_FRIEND + 4.0 <= T < T_FIGHT:
            items.append(act("friend", "r_stance", T, T_FRIEND + 4.0, LEDGE_FRIEND, "pingpong"))
        elif T_FIGHT <= T < T_TURN:
            items += duel(T, T_FIGHT, T_TURN, "friend", LEDGE_HERO, LEDGE_FRIEND, offset=1)
        elif T_TURN <= T < T_PAST:
            items += [act("hero", "h_salute", T, T_TURN, LEDGE_HERO, "once"), act("friend", "r_salute", T, T_TURN, LEDGE_FRIEND, "once")]
        elif T >= T_PAST:
            items.append(act("friend", "r_stance", T, T_PAST, LEDGE_FRIEND, "pingpong"))
            it = walk("hero", "h_walk_ur", [LEDGE_HERO, (205, 186), (268, 180), (290, 158)], T_PAST, T_PEAK + 0.3, T)
            items.append(it + (min(1.0, (T_PEAK + 0.3 - T) / 0.8),))
        draw_all(f, items, pl)
        snow(f, pl, T, float(np.clip((T - T_FRIEND) / 6.0, 0, 0.6)))
        return f

    # --- The summit: the moon, the snow and one man. ---
    def summit(T):
        pl = P["dingfeng"]
        f = pl["day"].copy()
        r = np.hypot(X - 70, Y - 70)
        rim = (r < 15) & pl["paper"]
        f[rim] = (196, 186, 150)
        moon = (r < 13.5) & pl["paper"]
        f[moon] = (250, 236, 176)
        shade = moon & (np.hypot(X - 75, Y - 66) < 11) & (bayer < 0.3)
        f[shade] = (236, 220, 160)
        halo = (r < 22) & pl["paper"] & ~rim & (bayer < 0.18)
        f[halo] = (232, 226, 200)
        if T < T_PEAK + 3.0:
            it = walk("hero", "h_walk_ur", [(176, 214), PEAK], T_PEAK, T_PEAK + 3.0, T)
            items = [it + (min(1.0, (T - T_PEAK) / 0.6),)]
        elif T < T_STILL:
            items = [act("hero", "h_form", T, T_PEAK + 3.0, PEAK)]
        else:
            items = [act("hero", "h_stand", T, T_STILL, PEAK, "pingpong")]
        draw_all(f, items, pl, light=(PEAK[0], PEAK[1] - 10, 30, (1.1, 1.1, 1.2)))
        snow(f, pl, T, 1.0)
        return f

    # --- The poem: vertical columns, right to left, one character on each beat. ---
    kai = ImageFont.truetype(font_path("simkai.ttf"), 20)
    glyphs = {}

    def glyph(ch):
        if ch not in glyphs:
            m = Image.new("L", (22, 22), 0)
            d = ImageDraw.Draw(m)
            d.fontmode = "1"
            d.text((1, 0), ch, font=kai, fill=255)
            stroke = np.asarray(m) > 0
            glyphs[ch] = (stroke, ndimage.binary_dilation(stroke) & ~stroke)
        return glyphs[ch]

    seal = Image.new("L", (14, 14), 0)
    ds = ImageDraw.Draw(seal)
    ds.fontmode = "1"
    ds.text((1, 0), "孤", font=ImageFont.truetype(font_path("simkai.ttf"), 13), fill=255)
    SEAL_MASK = np.asarray(seal) > 0
    X0, Y0, STEP, CH = 334, 18, 27, 21

    def draw_poem(f, T):
        started = [p for p in poem if p["at"] <= T]
        if not started:
            return
        stanza = started[-1]["stanza"]
        lines = [p for p in poem if p["stanza"] == stanza and p["at"] <= T]
        nxt = [p for p in poem if p["stanza"] == stanza + 1]
        fade = 1.0 if not nxt else float(np.clip((nxt[0]["at"] - T) / 0.8, 0, 1))
        for col, p in enumerate(lines):
            shown = min(len(p["zh"]), int((T - p["at"]) / BEAT) + 1)
            x = X0 - col * STEP
            for r, ch in enumerate(p["zh"][:shown]):
                m, halo = glyph(ch)
                y = Y0 + r * CH
                region = f[y:y + 22, x:x + 22].astype(np.float32)
                # The ink is written onto the scene. A faint paper glow around each stroke keeps it legible.
                h = halo & (bayer[y:y + 22, x:x + 22] < 0.55 * fade)
                region[h] = region[h] * 0.45 + paper * 0.55
                k = m & (bayer[y:y + 22, x:x + 22] < fade)
                region[k] = region[k] * 0.15 + INK_POEM * 0.85
                f[y:y + 22, x:x + 22] = region.astype(np.uint8)
        last = poem[-1]
        if stanza == last["stanza"] and T >= last["at"] + len(last["zh"]) * BEAT:
            x = X0 - (len(lines) - 1) * STEP + 4
            y = Y0 + len(last["zh"]) * CH + 4
            f[y:y + 14, x:x + 14] = SEAL
            f[y:y + 14, x:x + 14][SEAL_MASK] = paper

    title_kai = ImageFont.truetype(font_path("simkai.ttf"), 26)
    small = ImageFont.truetype(font_path("msgothic.ttc"), 12)
    state = {"last": None, "scene": None, "at": 0.0}

    def draw_title(f, T):
        a = min(1.0, (T - 0.6) / 0.4, (10.0 - T) / 0.6)
        if a <= 0:
            return
        m = Image.new("L", (G, G), 0)
        d = ImageDraw.Draw(m)
        d.fontmode = "1"
        for r, ch in enumerate("獨上高處"):
            d.text((22, 20 + r * 28), ch, font=title_kai, fill=255)
        d.text((14, 140), brief["title_id"], font=small, fill=255)
        keep = (np.asarray(m) > 0) & (bayer < a)
        f[keep] = INK_POEM

    def scene_at(T):
        if T < T_PLAT:
            return "courtyard", courtyard
        if T < T_LEDGE:
            return "platform", platform
        if T < T_PEAK:
            return "ledge", ledge
        return "summit", summit

    def draw(i, t, T):
        name, builder = scene_at(T)
        f = builder(T)
        if name != state["scene"]:
            state["scene"], state["at"] = name, T
        u = (T - state["at"]) / 0.4
        if u < 1 and state["last"] is not None:
            hide = bayer > u
            f[hide] = state["last"][hide]
        draw_title(f, T)
        draw_poem(f, T)
        caps.draw(f, T)
        if T < 0.6:
            f[bayer > T / 0.6] = paper
        left = ctx["end"] - T
        if left < 1.6:
            f[bayer > left / 1.6] = paper
        state["last"] = np.array(f, np.uint8)
        return f.astype(np.uint8)

    return draw
