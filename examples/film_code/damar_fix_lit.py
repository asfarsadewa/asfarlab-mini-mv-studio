# Snapping greys the amber. This copies the warm pixels of each lit plate back from its raw painting.
import numpy as np
from pathlib import Path
from PIL import Image

HERE = Path(__file__).parent
for name in ("desa_night", "lelep_lit", "omah_lelep"):
    raw = Image.open(HERE / f"{name}-raw.png").convert("RGB").resize((360, 360), Image.BOX)
    r = np.asarray(raw).astype(int)
    p = np.asarray(Image.open(HERE / f"{name}-360.png").convert("RGB")).copy()
    warm = (r[..., 0] - r[..., 2] > 45) & (r[..., 0] > 95)
    if name == "omah_lelep":
        # Only the window and its pool glow here. The timber is warm too.
        box = np.zeros(warm.shape, bool)
        box[195:275, 80:165] = True
        warm &= box
    # Keep colours on a coarse grid, so that the pixels stay flat.
    p[warm] = (r[warm] // 12 * 12).astype(np.uint8)
    Image.fromarray(p).save(HERE / f"{name}-360.png")
    print(name, int(warm.sum()))
