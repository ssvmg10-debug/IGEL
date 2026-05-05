"""
Convert PDFs to Markdown using Docling for comparison with marker-pdf.

Usage:
    python convert_docling.py                    # Convert all PDFs
    python convert_docling.py --test             # Test with first 2 PDFs only
    python convert_docling.py --file "name.pdf"  # Convert a single specific PDF
"""
import os
import sys
import glob
import time
import argparse
import traceback
import shutil

# Fix Windows symlink issue with Hugging Face Hub (requires Developer Mode otherwise)
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"


def _patch_hf_symlinks():
    """Patch huggingface_hub to use copies instead of symlinks on Windows."""
    try:
        import huggingface_hub.file_download as fd
        _original = fd._create_symlink

        def _create_symlink_or_copy(src, dst, new_blob=False):
            try:
                _original(src, dst, new_blob=new_blob)
            except OSError:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.exists(dst):
                    os.remove(dst)
                shutil.copy2(src, dst)

        fd._create_symlink = _create_symlink_or_copy
    except Exception:
        pass


_patch_hf_symlinks()


KB_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(KB_DIR, "docling_output")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")


def clean_filename(name: str) -> str:
    return name.replace("+", " ").replace("%20", " ")


def convert_single_pdf(pdf_path: str, converter) -> dict:
    fname = os.path.basename(pdf_path)
    md_name = clean_filename(os.path.splitext(fname)[0]) + ".md"
    md_path = os.path.join(OUTPUT_DIR, md_name)

    start = time.time()

    result = converter.convert(pdf_path)
    md_text = result.document.export_to_markdown()

    img_count = 0
    if hasattr(result.document, "pictures") and result.document.pictures:
        pdf_base = clean_filename(os.path.splitext(fname)[0]).replace(" ", "_")
        for idx, picture in enumerate(result.document.pictures):
            if hasattr(picture, "image") and picture.image and hasattr(picture.image, "pil_image"):
                img_name = f"{pdf_base}_img_{idx}.png"
                img_path = os.path.join(IMAGES_DIR, img_name)
                picture.image.pil_image.save(img_path)
                img_count += 1

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_text)

    elapsed = time.time() - start
    return {
        "filename": fname,
        "output": md_name,
        "chars": len(md_text),
        "images": img_count,
        "time": elapsed,
        "success": True,
    }


def convert_all(test_mode: bool = False, single_file: str = None):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)

    if single_file:
        pdf_files = [os.path.join(KB_DIR, single_file)]
        if not os.path.exists(pdf_files[0]):
            print(f"ERROR: File not found: {pdf_files[0]}")
            return
    else:
        pdf_files = sorted(glob.glob(os.path.join(KB_DIR, "*.pdf")))

    if test_mode:
        pdf_files = pdf_files[:2]

    total = len(pdf_files)
    print(f"{'='*60}")
    print(f"IGEL Knowledge Base PDF -> Markdown (Docling)")
    print(f"{'='*60}")
    print(f"PDFs to convert: {total}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"{'='*60}\n")

    print("Loading Docling models (this may take a minute on first run)...")
    from docling.document_converter import DocumentConverter
    converter = DocumentConverter()
    print("Models loaded.\n")

    success = 0
    failed = []
    total_time = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        fname = os.path.basename(pdf_path)
        print(f"[{i}/{total}] Converting: {clean_filename(fname)}")

        try:
            result = convert_single_pdf(pdf_path, converter)
            print(f"  -> {result['output']} ({result['chars']:,} chars, {result['images']} images, {result['time']:.1f}s)")
            success += 1
            total_time += result["time"]
        except Exception as e:
            print(f"  FAILED: {e}")
            traceback.print_exc()
            failed.append((fname, str(e)))

    print(f"\n{'='*60}")
    print(f"CONVERSION COMPLETE")
    print(f"{'='*60}")
    print(f"Successful: {success}/{total}")
    print(f"Total time: {total_time:.1f}s")
    if success > 0:
        print(f"Avg per PDF: {total_time/success:.1f}s")
    if failed:
        print(f"\nFAILED ({len(failed)}):")
        for name, err in failed:
            print(f"  - {clean_filename(name)}: {err}")
    print(f"\nOutput: {OUTPUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Knowledge Base PDFs to Markdown with Docling")
    parser.add_argument("--test", action="store_true", help="Test mode: convert only first 2 PDFs")
    parser.add_argument("--file", type=str, help="Convert a single specific PDF file")
    args = parser.parse_args()

    convert_all(test_mode=args.test, single_file=args.file)
