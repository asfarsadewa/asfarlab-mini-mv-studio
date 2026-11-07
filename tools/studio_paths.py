# Settings that differ between machines and studios. An environment variable overrides each default.
import json
import os
import platform
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WINDOWS_BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
MAC_BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
FONT_FALLBACKS = {
    "msgothic.ttc": ["msgothic.ttc", "NotoSansMonoCJKjp-Regular.otf", "NotoSansCJK-Regular.ttc", "NotoSansCJKjp-Regular.otf", "ヒラギノ角ゴシック W3.ttc", "Hiragino Sans GB.ttc"],
    "simsun.ttc": ["simsun.ttc", "NotoSansCJK-Regular.ttc", "NotoSansCJKsc-Regular.otf", "Hiragino Sans GB.ttc"],
}


def find_blender():
    """Returns BLENDER if it is set, then the default Windows path, then PATH, then the macOS app."""
    if os.environ.get("BLENDER"):
        return os.environ["BLENDER"]
    if platform.system() == "Windows" and Path(WINDOWS_BLENDER).exists():
        return WINDOWS_BLENDER
    return shutil.which("blender") or (MAC_BLENDER if Path(MAC_BLENDER).exists() else WINDOWS_BLENDER)


def font_dirs():
    if os.environ.get("FONT_DIR"):
        return [Path(os.environ["FONT_DIR"])]
    system = platform.system()
    if system == "Windows":
        return [Path("C:/Windows/Fonts")]
    if system == "Darwin":
        return [Path("/System/Library/Fonts"), Path("/Library/Fonts"), Path.home() / "Library/Fonts"]
    return [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), Path.home() / ".fonts", Path.home() / ".local/share/fonts"]


def font_path(name):
    """Finds a font by name, then by its known fallbacks. Captions stop on a font that lacks a glyph."""
    wanted = FONT_FALLBACKS.get(name, [name])
    dirs = font_dirs()
    for candidate in wanted:
        for folder in dirs:
            direct = folder / candidate
            if direct.exists():
                return str(direct)
            if folder.is_dir() and platform.system() != "Windows":
                match = next(folder.rglob(candidate), None)
                if match:
                    return str(match)
    raise SystemExit(f"No font found for {name}. Install one of {wanted}, or set FONT_DIR.")


def studio_handle():
    """The handle for the end card comes from studio.json. A blank handle leaves that line out."""
    path = ROOT / "studio.json"
    if not path.exists():
        return ""
    return json.loads(path.read_text(encoding="utf-8")).get("handle", "")


BLENDER = find_blender()
