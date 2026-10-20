"""How well does the perceptual hash survive edits, and does it false-match?

SPEC §17 item 5.

**The question.** `imagehash.phash` is what stops someone downloading a photo
and posting it as their own find (SPEC §9.7). Two numbers decide whether the
threshold of 8 bits is right:

  detection rate   a transformed copy of a photo is still recognised as it
  false-match rate two genuinely different photos are called the same

**The transforms**, chosen to be what actually happens to a stolen photo:
re-compression, resize, a small crop, a screenshot-style crop with a border,
mild brightness and contrast changes, a watermark, and slight rotation.

**The photos.** SPEC §17 asks for 50 of your own photos. Point `--photos` at a
directory and it uses those; they are not committed (CLAUDE.md "Git"). With no
directory it falls back to generated images, which exercise the code but are a
weaker test than real photographs, and the output says so.

    python sim/phash_sim.py --photos "C:/Users/you/Pictures/pagdandi"
"""
from __future__ import annotations

import argparse
import io
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

from common import bar_figure, write_results  # noqa: E402

from app.integrity.phash import hamming, is_match, phash_image  # noqa: E402
from app.config import cfg  # noqa: E402

SUPPORTED = {".jpg", ".jpeg", ".png", ".webp"}


# --------------------------------------------------------------------------- #
# Transforms a stolen photo typically goes through
# --------------------------------------------------------------------------- #

def recompress(img: Image.Image, quality: int = 55) -> Image.Image:
    buffer = io.BytesIO()
    img.convert("RGB").save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    return Image.open(buffer).copy()


def resize_half(img: Image.Image) -> Image.Image:
    return img.resize((max(1, img.width // 2), max(1, img.height // 2)), Image.LANCZOS)


def crop_small(img: Image.Image) -> Image.Image:
    """Trim 5 % from each edge -- the usual 'make it look different' crop."""
    dx, dy = int(img.width * 0.05), int(img.height * 0.05)
    return img.crop((dx, dy, img.width - dx, img.height - dy))


def crop_large(img: Image.Image) -> Image.Image:
    """Trim 20 % -- an aggressive crop that changes the composition."""
    dx, dy = int(img.width * 0.20), int(img.height * 0.20)
    return img.crop((dx, dy, img.width - dx, img.height - dy))


def brighten(img: Image.Image) -> Image.Image:
    return ImageEnhance.Brightness(img.convert("RGB")).enhance(1.25)


def contrast(img: Image.Image) -> Image.Image:
    return ImageEnhance.Contrast(img.convert("RGB")).enhance(1.3)


def watermark(img: Image.Image) -> Image.Image:
    out = img.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    text = "@someone_else"
    draw.rectangle(
        [8, out.height - 46, 8 + 230, out.height - 10], fill=(0, 0, 0)
    )
    draw.text((18, out.height - 38), text, fill=(255, 255, 255))
    return out


def rotate_small(img: Image.Image) -> Image.Image:
    return img.convert("RGB").rotate(3, expand=False, fillcolor=(0, 0, 0))


def screenshot(img: Image.Image) -> Image.Image:
    """A phone screenshot: the photo inset in a bordered frame."""
    out = Image.new("RGB", (img.width, int(img.height * 1.18)), (16, 16, 16))
    out.paste(img.convert("RGB"), (0, int(img.height * 0.09)))
    return out


TRANSFORMS = {
    "recompress q55": recompress,
    "resize 50%": resize_half,
    "crop 5%": crop_small,
    "crop 20%": crop_large,
    "brightness +25%": brighten,
    "contrast +30%": contrast,
    "watermark": watermark,
    "rotate 3deg": rotate_small,
    "screenshot frame": screenshot,
}


def load_photos(directory: Path | None, count: int) -> tuple[list[Image.Image], bool]:
    """Real photos from a directory, or generated stand-ins. (images, are_real)."""
    if directory and directory.is_dir():
        paths = [p for p in sorted(directory.iterdir()) if p.suffix.lower() in SUPPORTED]
        images = []
        for path in paths[:count]:
            with Image.open(path) as img:
                converted = img.convert("RGB")
                converted.thumbnail((1200, 1200), Image.LANCZOS)
                images.append(converted.copy())
        if images:
            return images, True

    # Generated stand-ins: layered landscapes with varied palettes and shapes.
    images = []
    for index in range(count):
        local = random.Random(index * 7919)
        width, height = 900, 1200
        base = (local.randrange(40, 220), local.randrange(40, 220), local.randrange(40, 220))
        img = Image.new("RGB", (width, height), base)
        draw = ImageDraw.Draw(img)
        for layer in range(local.randrange(3, 7)):
            colour = (
                local.randrange(20, 240),
                local.randrange(20, 240),
                local.randrange(20, 240),
            )
            top = local.randrange(0, height)
            points = [(0, height)]
            x = 0
            while x <= width:
                points.append((x, top - local.randrange(0, 180)))
                x += local.randrange(60, 160)
            points.append((width, height))
            draw.polygon(points, fill=colour)
        for _ in range(local.randrange(5, 20)):
            x, y = local.randrange(width), local.randrange(height)
            r = local.randrange(10, 90)
            draw.ellipse(
                [x - r, y - r, x + r, y + r],
                fill=(local.randrange(255), local.randrange(255), local.randrange(255)),
            )
        images.append(img)
    return images, False


def main() -> int:
    parser = argparse.ArgumentParser(description="pHash robustness (SPEC §17 item 5)")
    parser.add_argument("--photos", type=str, default=None, help="a directory of your own photos")
    parser.add_argument("--count", type=int, default=50)
    args = parser.parse_args()

    directory = Path(args.photos) if args.photos else None
    photos, are_real = load_photos(directory, args.count)
    threshold = int(cfg("integrity.phash_max_hamming", 8))

    originals = [phash_image(img) for img in photos]

    # --- detection: does a transformed copy still match its original? ------ #
    per_transform: dict[str, dict[str, float]] = {}
    for name, transform in TRANSFORMS.items():
        distances = []
        detected = 0
        for img, original in zip(photos, originals):
            changed = phash_image(transform(img))
            distance = hamming(original, changed)
            distances.append(distance)
            if distance <= threshold:
                detected += 1
        per_transform[name] = {
            "detection_rate": round(detected / len(photos), 4),
            "mean_hamming": round(sum(distances) / len(distances), 2),
            "max_hamming": max(distances),
        }

    overall_detected = sum(v["detection_rate"] for v in per_transform.values()) / len(per_transform)

    # --- false matches: do two different photos collide? ------------------- #
    pairs = 0
    false_matches = 0
    pair_distances = []
    for i in range(len(originals)):
        for j in range(i + 1, len(originals)):
            pairs += 1
            distance = hamming(originals[i], originals[j])
            pair_distances.append(distance)
            if distance <= threshold:
                false_matches += 1

    metrics = {
        "photos": len(photos),
        "photos_are_real": are_real,
        "threshold_hamming": threshold,
        "overall_detection_rate": round(overall_detected, 4),
        "per_transform": per_transform,
        "pairs_compared": pairs,
        "false_matches": false_matches,
        "false_match_rate": round(false_matches / pairs, 6) if pairs else 0.0,
        "mean_distance_between_different_photos": round(
            sum(pair_distances) / len(pair_distances), 2
        )
        if pair_distances
        else 0.0,
    }

    print(f"\npHash robustness ({len(photos)} photos, threshold <= {threshold} bits)")
    if not are_real:
        print("  NOTE: generated stand-in images, not photographs. Point --photos at")
        print("        a folder of your own photos for the number the report should quote.")
    print(f"\n  {'transform':<20} {'detected':>9} {'mean bits':>11} {'worst':>7}")
    for name, stats in per_transform.items():
        print(
            f"  {name:<20} {stats['detection_rate']:>8.0%} "
            f"{stats['mean_hamming']:>11.1f} {stats['max_hamming']:>7}"
        )
    print(f"\n  overall detection rate: {overall_detected:.1%}")
    print(
        f"  false-match rate: {metrics['false_match_rate']:.4%} "
        f"({false_matches} of {pairs:,} different-photo pairs)"
    )
    print(
        f"  mean distance between different photos: "
        f"{metrics['mean_distance_between_different_photos']} bits"
    )

    names = list(per_transform)
    figure = bar_figure(
        f"Detection rate per transform (threshold {threshold} bits, {len(photos)} photos)",
        names,
        [per_transform[n]["detection_rate"] for n in names],
        y_label="share still recognised",
    )

    path = write_results(
        "phash",
        metrics,
        seeds=[7],
        assumptions=[
            f"{len(photos)} source images, each put through {len(TRANSFORMS)} transforms.",
            "Real photographs" if are_real else
            "GENERATED stand-in images, not photographs -- a weaker test than real photos.",
            f"A match is a Hamming distance of at most {threshold} bits, the app's "
            "configured threshold (integrity.phash_max_hamming).",
            "False matches are counted over every pair of different source images.",
            "phash_image and hamming are the app's own functions (app.integrity.phash).",
        ],
        figure=figure,
    )
    print(f"\nWrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
