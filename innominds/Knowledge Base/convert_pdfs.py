"""
Convert all PDFs in Knowledge Base to Markdown using marker-pdf.

Each PDF gets its own output folder with:
  - <name>.md         (the markdown file)
  - images/           (all images extracted from that PDF)

This ensures clear relationship between each PDF and its converted content.

Usage:
    python convert_pdfs.py --use_llm          # Full batch with Azure OpenAI LLM (recommended)
    python convert_pdfs.py                    # Full batch without LLM
    python convert_pdfs.py --test             # Test with first 2 PDFs only
    python convert_pdfs.py --file "name.pdf"  # Convert a single specific PDF
"""
import os
import sys
import glob
import time
import json
import argparse
import traceback


KB_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(KB_DIR, "markdown_output")

AZURE_CONFIG = {
    "azure_api_key": os.environ.get("AZURE_API_KEY", ""),
    "azure_endpoint": os.environ.get("AZURE_ENDPOINT", ""),
    "deployment_name": os.environ.get("AZURE_DEPLOYMENT", ""),
    "azure_api_version": os.environ.get("AZURE_API_VERSION", "2024-02-01"),
}


def clean_filename(name: str) -> str:
    """Normalize URL-encoded filenames to readable names."""
    return name.replace("+", " ").replace("%20", " ")


def get_pdf_output_dir(pdf_filename: str) -> str:
    """Each PDF gets its own folder inside markdown_output/ for clear relationship."""
    base = clean_filename(os.path.splitext(pdf_filename)[0])
    safe_dir = base.replace(" ", "_").replace("(", "").replace(")", "").replace(",", "")
    return os.path.join(OUTPUT_DIR, safe_dir)


def save_images(rendered, pdf_filename: str, md_text: str, pdf_out_dir: str) -> tuple:
    """Extract ALL images from rendered output, save them, update markdown references."""
    images_dir = os.path.join(pdf_out_dir, "images")
    img_count = 0

    if not hasattr(rendered, "images") or not rendered.images:
        return md_text, img_count

    os.makedirs(images_dir, exist_ok=True)

    for img_name, img_data in rendered.images.items():
        img_path = os.path.join(images_dir, img_name)

        try:
            if hasattr(img_data, "save"):
                img_data.save(img_path)
                img_count += 1
            elif isinstance(img_data, bytes):
                with open(img_path, "wb") as f:
                    f.write(img_data)
                img_count += 1
            elif isinstance(img_data, str):
                import base64
                with open(img_path, "wb") as f:
                    f.write(base64.b64decode(img_data))
                img_count += 1
        except Exception as e:
            print(f"    [WARN] Could not save image {img_name}: {e}")

        md_text = md_text.replace(img_name, f"images/{img_name}")

    return md_text, img_count


def add_source_header(md_text: str, pdf_filename: str) -> str:
    """Add source metadata at the top of the markdown for traceability."""
    clean_name = clean_filename(pdf_filename)
    header = f"<!-- Source: {clean_name} -->\n<!-- Converted with marker-pdf + Azure OpenAI LLM -->\n\n"
    return header + md_text


def convert_single_pdf(pdf_path: str, converter) -> dict:
    """Convert a single PDF preserving ALL content (images, tables, text, math, forms)."""
    fname = os.path.basename(pdf_path)
    clean_name = clean_filename(os.path.splitext(fname)[0])
    pdf_out_dir = get_pdf_output_dir(fname)
    os.makedirs(pdf_out_dir, exist_ok=True)

    md_name = clean_name + ".md"
    md_path = os.path.join(pdf_out_dir, md_name)

    start = time.time()

    rendered = converter(pdf_path)
    md_text = rendered.markdown

    md_text, img_count = save_images(rendered, fname, md_text, pdf_out_dir)
    md_text = add_source_header(md_text, fname)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_text)

    elapsed = time.time() - start

    metadata = {
        "source_pdf": fname,
        "output_md": md_name,
        "images_extracted": img_count,
        "char_count": len(md_text),
        "conversion_time_seconds": round(elapsed, 1),
    }
    if hasattr(rendered, "metadata") and rendered.metadata:
        metadata["page_count"] = len(rendered.metadata.get("page_stats", []))

    with open(os.path.join(pdf_out_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    return {
        "filename": fname,
        "output": md_name,
        "chars": len(md_text),
        "images": img_count,
        "time": elapsed,
        "success": True,
    }


def build_converter(use_llm: bool):
    """Build marker PdfConverter configured for maximum context extraction."""
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.config.parser import ConfigParser

    config = {
        "output_format": "markdown",
        "force_ocr": True,
    }

    if use_llm:
        config["use_llm"] = True
        config["llm_service"] = "marker.services.azure_openai.AzureOpenAIService"
        config.update(AZURE_CONFIG)

    config_parser = ConfigParser(config)

    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service() if use_llm else None,
    )

    return converter


def convert_all(use_llm: bool = False, test_mode: bool = False, single_file: str = None, resume: bool = False):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if single_file:
        pdf_files = [os.path.join(KB_DIR, single_file)]
        if not os.path.exists(pdf_files[0]):
            print(f"ERROR: File not found: {pdf_files[0]}")
            return
    else:
        pdf_files = sorted(glob.glob(os.path.join(KB_DIR, "*.pdf")))

    if test_mode:
        pdf_files = pdf_files[:2]

    if resume:
        remaining = []
        for pf in pdf_files:
            out_dir = get_pdf_output_dir(os.path.basename(pf))
            md_name = clean_filename(os.path.splitext(os.path.basename(pf))[0]) + ".md"
            md_path = os.path.join(out_dir, md_name)
            if os.path.exists(md_path):
                print(f"  [SKIP] Already converted: {clean_filename(os.path.basename(pf))}")
            else:
                remaining.append(pf)
        pdf_files = remaining

    total = len(pdf_files)
    print(f"{'='*60}")
    print(f"IGEL Knowledge Base PDF -> Markdown Converter")
    print(f"{'='*60}")
    print(f"PDFs to convert: {total}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"LLM mode: {'Azure OpenAI (' + AZURE_CONFIG['deployment_name'] + ')' if use_llm else 'Disabled'}")
    print(f"Force OCR: Enabled (captures all text including from images)")
    print(f"Image extraction: Enabled")
    print(f"Table detection: Enabled (LLM merges cross-page tables)" if use_llm else "")
    print(f"{'='*60}\n")

    print("Loading marker models...")
    converter = build_converter(use_llm)
    print("Models loaded.\n")

    success = 0
    failed = []
    total_time = 0
    all_results = []

    for i, pdf_path in enumerate(pdf_files, 1):
        fname = os.path.basename(pdf_path)
        print(f"[{i}/{total}] Converting: {clean_filename(fname)}")

        try:
            result = convert_single_pdf(pdf_path, converter)
            print(f"  -> {result['output']} ({result['chars']:,} chars, {result['images']} images, {result['time']:.1f}s)")
            success += 1
            total_time += result["time"]
            all_results.append(result)
        except Exception as e:
            print(f"  FAILED: {e}")
            traceback.print_exc()
            failed.append((fname, str(e)))

    # Write conversion summary
    summary = {
        "total_pdfs": total,
        "successful": success,
        "failed": len(failed),
        "total_time_seconds": round(total_time, 1),
        "avg_time_per_pdf": round(total_time / success, 1) if success > 0 else 0,
        "total_images_extracted": sum(r["images"] for r in all_results),
        "total_chars": sum(r["chars"] for r in all_results),
        "failed_files": [{"file": name, "error": err} for name, err in failed],
        "converted_files": [{"source": r["filename"], "output": r["output"]} for r in all_results],
    }
    with open(os.path.join(OUTPUT_DIR, "conversion_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    # Write index file for easy navigation
    with open(os.path.join(OUTPUT_DIR, "INDEX.md"), "w") as f:
        f.write("# IGEL Knowledge Base - Converted Documents\n\n")
        f.write(f"Total documents: {success}/{total} converted successfully\n\n")
        f.write("## Documents\n\n")
        for r in sorted(all_results, key=lambda x: x["output"]):
            dir_name = get_pdf_output_dir(r["filename"]).replace(OUTPUT_DIR + os.sep, "")
            f.write(f"- [{clean_filename(os.path.splitext(r['filename'])[0])}]({dir_name}/{r['output']})")
            f.write(f" ({r['images']} images)\n")
        if failed:
            f.write("\n## Failed Conversions\n\n")
            for name, err in failed:
                f.write(f"- {clean_filename(name)}: {err}\n")

    print(f"\n{'='*60}")
    print(f"CONVERSION COMPLETE")
    print(f"{'='*60}")
    print(f"Successful: {success}/{total}")
    print(f"Total time: {total_time:.1f}s")
    if success > 0:
        print(f"Avg per PDF: {total_time/success:.1f}s")
    print(f"Total images extracted: {sum(r['images'] for r in all_results)}")
    if failed:
        print(f"\nFAILED ({len(failed)}):")
        for name, err in failed:
            print(f"  - {clean_filename(name)}: {err}")
    print(f"\nOutput: {OUTPUT_DIR}")
    print(f"Index: {os.path.join(OUTPUT_DIR, 'INDEX.md')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Knowledge Base PDFs to Markdown")
    parser.add_argument("--use_llm", action="store_true", help="Use Azure OpenAI LLM for highest accuracy")
    parser.add_argument("--test", action="store_true", help="Test mode: convert only first 2 PDFs")
    parser.add_argument("--file", type=str, help="Convert a single specific PDF file")
    parser.add_argument("--resume", action="store_true", help="Skip PDFs that already have output folders")
    args = parser.parse_args()

    convert_all(use_llm=args.use_llm, test_mode=args.test, single_file=args.file, resume=args.resume)
