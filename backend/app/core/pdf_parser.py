import re
import time
import logging
import gc
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

import fitz  # PyMuPDF
import statistics
import uuid # Import uuid at the top of the file

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("HybridPDFOutlineExtractor")


# --- Helper Functions & Dataclasses ---

def _normalize_text(text: str) -> str:
    """Normalizes text for robust comparison."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


class TextBlock:
    """Represents a block of text extracted from a PDF page."""

    def __init__(self, text: str, bbox: Tuple[float, float, float, float], page_num: int, size: float, font: str,
                 flags: int):
        self.text = (text or "").strip()
        self.bbox = fitz.Rect(bbox)
        self.page_num = page_num
        self.size = round(float(size), 2)
        self.font = font or ""
        self.flags = flags or 0
        self.is_bold = self._is_bold_font()

    def _is_bold_font(self) -> bool:
        name = (self.font or "").lower()
        if any(k in name for k in ("bold", "black", "heavy", "demi")):
            return True
        return bool(self.flags & 16)


# --- The Main Extractor Class ---
class HybridPDFOutlineExtractor:
    """
    A class to extract document outlines from PDF files using a hybrid approach.
    """

    def __init__(self):
        self.heading_patterns = [
            re.compile(r'^(Chapter|Section|Part)\s+[\dIVX]+', re.IGNORECASE),
            re.compile(r'^\d+\.\d*(\.\d*)*\s+[A-Z]'),  # Matches 1., 1.1, 1.1.1 etc.
            re.compile(r'^(Abstract|Introduction|Conclusion|References|Appendix)', re.IGNORECASE),
        ]
        self.junk_words = {'name', 'age', 's.no', 'date', 'signature'}

    def find_document_title(self, doc: fitz.Document) -> str:
        """Finds the main title of the document."""
        candidates = []
        max_pages = min(len(doc), 3)
        for p in range(max_pages):
            page = doc[p]
            blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_DICT).get("blocks", [])
            for block in blocks:
                if block.get("type") != 0: continue
                for line in block.get("lines", []):
                    if len(line.get("spans", [])) != 1: continue
                    span = line["spans"][0]
                    txt = (span.get("text") or "").strip()
                    if len(txt) < 4 or len(txt) > 150 or re.fullmatch(r'[\d\.]+', txt): continue

                    score = span.get("size", 0) * 1.5
                    if p == 0: score += 25
                    if "bold" in (span.get("font") or "").lower(): score += 10
                    if span.get("bbox", [0, 0, 0, 0])[1] < 160: score += 20

                    if score > 40:
                        candidates.append((re.sub(r'\s+', ' ', txt), score))

        if candidates:
            return max(candidates, key=lambda x: x[1])[0]

        meta_title = doc.metadata.get("title")
        return meta_title.strip() if meta_title else "Untitled Document"

    def process_toc(self, toc: List[Tuple]) -> List[Dict[str, Any]]:
        """Cleans and standardizes TOC entries."""
        logger.debug(f"Processing TOC. Raw TOC entries: {len(toc)}")
        outline = []
        seen = set()
        for level, title, page in toc:
            if not title or not (1 <= level <= 3):
                logger.debug(f"Skipping TOC entry: level={level}, title='{title}'")
                continue
            t = re.sub(r'(\.{3,}|[\s\d]+)$', '', title).strip()
            if len(t) < 3:
                logger.debug(f"Skipping TOC entry (too short): '{t}'")
                continue
            key = (t.lower(), page)
            if key in seen:
                logger.debug(f"Skipping duplicate TOC entry: '{t}' on page {page}")
                continue
            seen.add(key)
            outline.append({"level": f"H{level}", "text": t, "page": page, "section_id": f"sec_{uuid.uuid4().hex}"})
        logger.debug(f"Finished processing TOC. Usable outline items: {len(outline)}")
        return sorted(outline, key=lambda x: x["page"])

    def _get_all_text_blocks(self, doc: fitz.Document) -> List[TextBlock]:
        """Extracts and groups all text lines into semantic blocks for the entire document."""
        all_lines = []
        for page_num, page in enumerate(doc):
            try:
                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_DICT).get("blocks", [])
                for block in blocks:
                    if block.get("type") != 0: continue
                    for line in block.get("lines", []):
                        spans = [s for s in line.get("spans", []) if (s.get("text") or "").strip()]
                        if not spans: continue
                        full_text = " ".join(s["text"].strip() for s in spans)
                        rect = fitz.Rect(spans[0]["bbox"])
                        for s in spans[1:]: rect.include_rect(s["bbox"])
                        first = spans[0]
                        all_lines.append(
                            TextBlock(full_text, tuple(rect), page_num, first["size"], first["font"], first["flags"]))
            except Exception as e:
                logger.debug(f"Could not parse page {page_num}: {e}")
        logger.debug(f"Extracted {len(all_lines)} raw text lines from document.")

        # Group lines into semantic blocks
        if not all_lines:
            logger.debug("No text lines to group into blocks.")
            return []
        grouped = []
        current = [all_lines[0]]
        for b in all_lines[1:]:
            prev = current[-1]
            if (prev.page_num == b.page_num and abs(prev.size - b.size) < 1.0 and 0 <= (
                    b.bbox.y0 - prev.bbox.y1) < prev.size * 0.5):
                current.append(b)
            else:
                if len(current) > 1:
                    merged_text = " ".join(x.text for x in current)
                    merged_bbox = fitz.Rect()
                    for x in current: merged_bbox.include_rect(x.bbox)
                    first = current[0]
                    grouped.append(
                        TextBlock(merged_text, tuple(merged_bbox), first.page_num, first.size, first.font, first.flags))
                else:
                    grouped.append(current[0])
                current = [b]
        if current:
            if len(current) > 1:
                merged_text = " ".join(x.text for x in current)
                merged_bbox = fitz.Rect()
                for x in current: merged_bbox.include_rect(x.bbox)
                first = current[0]
                grouped.append(
                    TextBlock(merged_text, tuple(merged_bbox), first.page_num, first.size, first.font, first.flags))
            else:
                grouped.append(current[0])
        logger.debug(f"Grouped text into {len(grouped)} semantic blocks.")
        return grouped

    def extract_visual_outline(self, all_blocks: List[TextBlock]) -> List[Dict[str, Any]]:
        """Extracts and classifies headings from a list of semantic text blocks."""
        logger.debug(f"Starting visual outline extraction from {len(all_blocks)} text blocks.")
        if not all_blocks:
            logger.debug("No text blocks provided for visual outline extraction.")
            return []

        body_sizes = [b.size for b in all_blocks if len(b.text.split()) > 5 and b.size > 6.0]
        body_size = statistics.median(body_sizes) if body_sizes else 10.0
        logger.debug(f"Estimated body text size: {body_size}")

        headings = []
        for b in all_blocks:
            score = 0
            if b.size > body_size + 1.0: score += 1
            if b.is_bold: score += 1
            if len(b.text.split()) <= 12: score += 1
            if any(pat.match(b.text) for pat in self.heading_patterns): score += 2
            if b.text.lower() in self.junk_words: score = 0

            if score >= 2:  # HEADING_SCORE_MIN
                headings.append({"text": b.text, "size": b.size, "page": b.page_num + 1})
        logger.debug(f"Identified {len(headings)} potential headings.")

        if not headings:
            logger.debug("No potential headings found during visual extraction.")
            return []

        # Classify levels
        unique_sizes = sorted(list(set(h['size'] for h in headings)), reverse=True)
        size_to_level = {size: f"H{i + 1}" for i, size in enumerate(unique_sizes[:3])}
        logger.debug(f"Unique heading sizes: {unique_sizes}, mapped to levels: {size_to_level}")

        classified_headings = []
        for h in headings:
            if h['size'] in size_to_level:
                h['level'] = size_to_level[h['size']]
                h['section_id'] = f"sec_{uuid.uuid4().hex}" # Generate a unique section_id
                del h['size']  # Clean up the dictionary
                classified_headings.append(h)
        logger.debug(f"Classified {len(classified_headings)} final headings.")

        return sorted(classified_headings, key=lambda x: (x["page"], int(x["level"][1:])))

    def add_section_text(self, doc: fitz.Document, outline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Adds the full text content to each section in the outline."""
        logger.debug(f"Adding section text for {len(outline)} outline items.")
        for i, section in enumerate(outline):
            start_page = section['page']
            # Determine the end page for the current section's content
            end_page = outline[i + 1]['page'] if i + 1 < len(outline) else len(doc)

            section_text = []
            for page_num in range(start_page - 1, end_page):
                if 0 <= page_num < len(doc):
                    section_text.append(doc[page_num].get_text("text"))

            section['section_text'] = " ".join(section_text).replace('\n', ' ').strip()
            logger.debug(f"Added text for section '{section.get('text', 'N/A')}' from page {start_page} to {end_page}. Text length: {len(section['section_text'])}")
        return outline

    def process_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """Main processing function for a single PDF."""
        logger.info(f"Starting PDF processing for: {pdf_path.name}")
        try:
            doc = fitz.open(str(pdf_path))
            logger.debug(f"Successfully opened PDF: {pdf_path.name} with {doc.page_count} pages.")
        except Exception as e:
            logger.error(f"Cannot open {pdf_path.name}: {e}")
            return {"title": pdf_path.stem, "outline": [], "total_pages": 0} # Return 0 pages on error

        try:
            title = self.find_document_title(doc)
            logger.debug(f"Document title identified: '{title}'")

            outline = self.process_toc(doc.get_toc())
            if outline:
                logger.info(f"Found {len(outline)} outline entries from TOC for {pdf_path.name}.")
            else:
                logger.info(f"No usable TOC for {pdf_path.name}, attempting visual extraction.")
                all_blocks = self._get_all_text_blocks(doc)
                outline = self.extract_visual_outline(all_blocks)
                if outline:
                    logger.info(f"Found {len(outline)} outline entries from visual extraction for {pdf_path.name}.")
                else:
                    logger.warning(f"No outline found via TOC or visual extraction for {pdf_path.name}.")

            # Add the full section text to the final outline
            final_outline = self.add_section_text(doc, outline)
            logger.info(f"Finished adding section text. Final outline has {len(final_outline)} items.")

            return {"title": title, "outline": final_outline, "total_pages": doc.page_count}

        except Exception as e:
            logger.error(f"Error processing {pdf_path.name}: {e}", exc_info=True)
            return {"title": pdf_path.stem, "outline": [], "total_pages": 0}
        finally:
            doc.close()
            gc.collect()
        logger.info(f"Finished PDF processing for: {pdf_path.name}")

def get_quad_points_for_text(
    pdf_path: Path,
    page_num: int,
    text_to_find: str
) -> List[List[float]]:
    """
    Extracts quad points for all occurrences of a given text string on a specific page of a PDF.
    Returns a list of quad point arrays, where each quad point array is [x0, y0, x1, y0, x1, y1, x0, y1].
    """
    quad_points_list = []
    try:
        doc = fitz.open(str(pdf_path))
        if page_num < 0 or page_num >= len(doc):
            logger.warning(f"Page number {page_num} out of range for {pdf_path.name}.")
            doc.close()
            return []

        page = doc.load_page(page_num)
        # search_for returns a list of fitz.Rect objects
        text_instances = page.search_for(text_to_find)

        for inst in text_instances:
            # fitz.Rect is (x0, y0, x1, y1)
            # Adobe quadPoints format: [x0, y0, x1, y0, x1, y1, x0, y1]
            quad_points = [
                inst.x0, inst.y0,  # Top-left
                inst.x1, inst.y0,  # Top-right
                inst.x1, inst.y1,  # Bottom-right
                inst.x0, inst.y1   # Bottom-left
            ]
            quad_points_list.append(quad_points)
        doc.close()
        logger.info(f"Found {len(quad_points_list)} instances of '{text_to_find}' on page {page_num} of {pdf_path.name}.")
    except Exception as e:
        logger.error(f"Error extracting quad points for '{text_to_find}' on page {page_num} of {pdf_path.name}: {e}", exc_info=True)
    return quad_points_list

def get_pdf_parser() -> HybridPDFOutlineExtractor:
    """
    Dependency injection function for HybridPDFOutlineExtractor.
    """
    return HybridPDFOutlineExtractor()

