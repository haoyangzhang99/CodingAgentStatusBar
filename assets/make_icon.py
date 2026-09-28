"""Draw the OpenCode Status Bar app icon and write AppIcon.png and AppIcon.icns.

The style follows the OpenCode desktop icon (dark rounded square, flat blocky
white and light-gray shapes separated by thin black lines), with an original
glyph: a menu bar strip holding a status item, and a dropdown panel below it.

Run on macOS from the project folder:  uv run python assets/make_icon.py
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

import AppKit

SIZE = 1024
OUT = Path(__file__).resolve().parent


def gray(level: int, alpha: float = 1.0):
    # Device colors are written to the bitmap unconverted; the file is tagged sRGB below.
    v = level / 255
    return AppKit.NSColor.colorWithDeviceRed_green_blue_alpha_(v, v, v, alpha)


def rect(x: float, y: float, w: float, h: float):
    """A rectangle in top-left-origin coordinates (AppKit's origin is bottom-left)."""
    return AppKit.NSMakeRect(x, SIZE - y - h, w, h)


def block(x, y, w, h, fill, outline=6):
    """A flat block with a thin black outline, as in OpenCode's logo."""
    gray(0).setFill()
    AppKit.NSRectFill(rect(x - outline, y - outline, w + 2 * outline, h + 2 * outline))
    fill.setFill()
    AppKit.NSRectFill(rect(x, y, w, h))


def draw():
    # Standard macOS icon grid: 824 x 824 rounded square centred on 1024 x 1024.
    tile = rect(100, 92, 824, 824)
    shape = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(tile, 185, 185)

    AppKit.NSGraphicsContext.saveGraphicsState()
    shadow = AppKit.NSShadow.alloc().init()
    shadow.setShadowOffset_((0, -10))
    shadow.setShadowBlurRadius_(22)
    shadow.setShadowColor_(gray(0, 0.35))
    shadow.set()
    gray(25).setFill()
    shape.fill()
    AppKit.NSGraphicsContext.restoreGraphicsState()

    # Background: OpenCode's near-black gradient as macOS draws it, lighter at the top.
    gradient = AppKit.NSGradient.alloc().initWithStartingColor_endingColor_(gray(53), gray(25))
    gradient.drawInBezierPath_angle_(shape, -90)

    # Subtle edge: darker rim, faint highlight along the top.
    AppKit.NSGraphicsContext.saveGraphicsState()
    shape.addClip()
    rim = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(tile, 185, 185)
    rim.setLineWidth_(8)
    gray(0, 0.45).setStroke()
    rim.stroke()
    gray(255, 0.12).setFill()
    AppKit.NSRectFill(rect(100, 92, 824, 3))
    AppKit.NSGraphicsContext.restoreGraphicsState()

    # Menu bar strip, with a dark status item near its right end.
    block(212, 262, 600, 116, gray(253))
    block(662, 292, 80, 56, gray(18), outline=0)

    # Dropdown panel hanging below the status item.
    block(452, 436, 360, 372, gray(183))
    # Menu rows inside the panel, in OpenCode's mid gray.
    for i, width in enumerate((264, 264, 176)):
        block(500, 488 + i * 104, width, 52, gray(82), outline=0)


def main():
    rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, SIZE, SIZE, 8, 4, True, False, AppKit.NSDeviceRGBColorSpace, 0, 0
    )
    rep.setSize_((SIZE, SIZE))
    context = AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    AppKit.NSGraphicsContext.saveGraphicsState()
    AppKit.NSGraphicsContext.setCurrentContext_(context)
    context.setImageInterpolation_(AppKit.NSImageInterpolationHigh)
    draw()
    context.flushGraphics()
    AppKit.NSGraphicsContext.restoreGraphicsState()
    rep = rep.bitmapImageRepByRetaggingWithColorSpace_(AppKit.NSColorSpace.sRGBColorSpace())

    master = OUT / "AppIcon.png"
    rep.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, None).writeToFile_atomically_(
        str(master), True
    )

    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "AppIcon.iconset"
        iconset.mkdir()
        for points in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                px = points * scale
                name = f"icon_{points}x{points}{'@2x' if scale == 2 else ''}.png"
                if px == SIZE:
                    shutil.copy(master, iconset / name)
                else:
                    subprocess.run(
                        ["sips", "-z", str(px), str(px), str(master), "--out", str(iconset / name)],
                        check=True, capture_output=True,
                    )
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(OUT / "AppIcon.icns")],
            check=True,
        )
    print(f"Wrote {master} and {OUT / 'AppIcon.icns'}")


if __name__ == "__main__":
    main()
