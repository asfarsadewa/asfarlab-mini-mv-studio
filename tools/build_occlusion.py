# Builds one occlusion label map per plate from traced shapes.
# Each shape holds a polygon and a base row: the screen row where the object meets the ground.
# With "refine", GrabCut snaps the polygon to the edges of the painting. A result that moves too far is rejected.
# Pixel value 0 means no occluder. Value n means shape n. Each map gets a preview for review.
# Usage: python tools/build_occlusion.py mvs/<id> <plate_suffix>
import json, sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

root = Path(sys.argv[1])
suffix = sys.argv[2] if len(sys.argv) > 2 else "-360"
shapes = json.loads((root / "occluders.json").read_text())
out_dir = root / "occlusion"
out_dir.mkdir(exist_ok=True)
for plate_name, items in shapes.items():
    plate = np.asarray(Image.open(root / "plates" / f"{plate_name}{suffix}.png").convert("RGB"))
    h, w, _ = plate.shape
    labels = np.zeros((h, w), np.uint8)
    report = []
    # Paint far objects first, so a nearer object wins where shapes overlap.
    order = sorted(((n, i) for n, i in enumerate(items, 1) if "poly" in i), key=lambda kv: kv[1]["base"])
    for n, item in order:
        poly = np.zeros((h, w), np.uint8)
        cv2.fillPoly(poly, [np.array(item["poly"], np.int32)], 1)
        mask = poly.astype(bool)
        note = "traced"
        if item.get("refine"):
            kernel = np.ones((3, 3), np.uint8)
            inner = cv2.erode(poly, kernel, iterations=2).astype(bool)
            outer = cv2.dilate(poly, kernel, iterations=3).astype(bool)
            gc = np.full((h, w), cv2.GC_BGD, np.uint8)
            gc[outer] = cv2.GC_PR_BGD
            gc[poly.astype(bool)] = cv2.GC_PR_FGD
            gc[inner] = cv2.GC_FGD
            cv2.setRNGSeed(1)
            cv2.grabCut(plate[..., ::-1].copy(), gc, None, np.zeros((1, 65)), np.zeros((1, 65)), 5, cv2.GC_INIT_WITH_MASK)
            # Refinement may trim the trace, or grow it by 1 pixel. A larger spill would hide the legs of a nearby person.
            limit = cv2.dilate(poly, kernel, iterations=1).astype(bool)
            refined = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)) & limit
            change = (refined ^ mask).sum() / max(mask.sum(), 1)
            if change < 0.25:
                mask, note = refined, f"refined {change:.0%}"
            else:
                note = f"kept trace, refine moved {change:.0%}"
        labels[mask] = n
        report.append(f"{item['name']}: {int(mask.sum())} px, {note}")
    # Empty paper never hides anything.
    paper = (plate == plate[0, 0]).all(axis=2)
    labels[paper] = 0
    Image.fromarray(labels).save(out_dir / f"{plate_name}.png")
    (out_dir / f"{plate_name}.json").write_text(json.dumps({str(i): s.get("base", 0) for i, s in enumerate(items, 1)}))
    tint = plate.astype(np.float32)
    colours = np.array([[0, 0, 0], [255, 0, 90], [0, 220, 255], [255, 220, 0], [90, 255, 90], [190, 90, 255], [255, 140, 0], [0, 120, 255]], np.float32)
    active = labels > 0
    tint[active] = tint[active] * 0.45 + colours[labels[active] % len(colours)] * 0.55
    Image.fromarray(tint.astype(np.uint8)).resize((w * 2, h * 2), Image.NEAREST).save(out_dir / f"{plate_name}_preview.png")
    print(plate_name, "; ".join(report))
