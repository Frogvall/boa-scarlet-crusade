#!/usr/bin/env python3
"""Compress large Flate-encoded RGB illustrations in PDFs, preserving alpha masks."""
import argparse
import io
import sys
from pathlib import Path

import fitz
from PIL import Image


def optimize(source: Path, target: Path, quality: int, threshold_kib: int, min_saving: float) -> None:
    if not source.is_file():
        raise ValueError(f"Input file does not exist: {source}")
    if source.resolve() == target.resolve():
        raise ValueError("Input and output must be different files")
    if target.exists():
        raise ValueError(f"Output already exists (refusing to overwrite): {target}")
    if not target.parent.is_dir():
        raise ValueError(f"Output directory does not exist: {target.parent}")

    doc = fitz.open(str(source))
    try:
        images = {}
        mask_xrefs = set()
        for page in doc:
            for item in page.get_images(full=True):
                images[item[0]] = item
                if item[1]:
                    mask_xrefs.add(item[1])

        transformed = 0
        before = 0
        after = 0
        for xref in sorted(images):
            if xref in mask_xrefs:
                continue
            if doc.xref_get_key(xref, "Filter")[1] != "/FlateDecode":
                continue
            raw_size = len(doc.xref_stream_raw(xref))
            if raw_size < threshold_kib * 1024:
                continue
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n != 3 or pix.colorspace != fitz.csRGB:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                rgb = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                buffer = io.BytesIO()
                rgb.save(buffer, format="JPEG", quality=quality, subsampling=0, optimize=True)
                jpeg = buffer.getvalue()
                if len(jpeg) >= raw_size * (1.0 - min_saving):
                    continue
                doc.update_stream(xref, jpeg, compress=False)
                doc.xref_set_key(xref, "Filter", "/DCTDecode")
                doc.xref_set_key(xref, "ColorSpace", "/DeviceRGB")
                doc.xref_set_key(xref, "DecodeParms", "null")
                transformed += 1
                before += raw_size
                after += len(jpeg)
            except Exception as exc:
                print(f"Warning: skipping image xref {xref}: {exc}", file=sys.stderr)

        # Save to a temporary file, so errors don't leave a partial output behind.
        temp = target.with_name(target.name + ".tmp")
        if temp.exists():
            raise ValueError(f"Temporary output already exists: {temp}")
        try:
            doc.save(str(temp), garbage=4, deflate=True)
            temp.rename(target)
        finally:
            if temp.exists():
                temp.unlink()
        orig_bytes = source.stat().st_size
        new_bytes = target.stat().st_size
        print(f"Optimized {transformed} image objects (of {len(images)} referenced images).")
        print(f"Compressed image streams: {before / (1024**2):.1f} MiB -> {after / (1024**2):.1f} MiB")
        print(f"PDF: {orig_bytes / (1024**2):.1f} MiB -> {new_bytes / (1024**2):.1f} MiB "
              f"({(1 - new_bytes / orig_bytes) * 100:.1f}% smaller)")
        print(f"Output: {target}")
    finally:
        doc.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Input PDF path")
    parser.add_argument("output", type=Path, help="Output PDF path")
    parser.add_argument("--quality", type=int, default=84, help="JPEG quality (default: 84)")
    parser.add_argument("--threshold-kib", type=int, default=100, help="Ignore image streams below this size (default: 100)")
    parser.add_argument("--min-saving", type=float, default=0.05, help="Minimum proportional saving (default: 0.05)")
    args = parser.parse_args()
    if not (1 <= args.quality <= 100):
        parser.error("--quality must be between 1 and 100")
    if args.threshold_kib < 0 or not (0 <= args.min_saving < 1):
        parser.error("invalid threshold or min-saving")
    try:
        optimize(args.input, args.output, args.quality, args.threshold_kib, args.min_saving)
    except Exception as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
