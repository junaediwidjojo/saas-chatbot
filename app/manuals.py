"""Step 05 product catalog and PDF manual extraction with page metadata."""

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

MAX_MANUAL_BYTES = 20 * 1024 * 1024
MAX_MANUAL_PAGES = 200
MAX_PRODUCTS = 50
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
PRODUCT_FIELDS = {"id", "name", "category", "aliases", "visual_features", "manual"}

# pdfminer logs noisy font warnings for malformed files; the errors we need are raised.
logging.getLogger("pdfminer").setLevel(logging.ERROR)


class CatalogError(Exception):
    pass


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    category: str
    aliases: tuple[str, ...]
    visual_features: str
    manual: Path | None

    @property
    def manual_title(self) -> str:
        return f"Panduan {self.name}"

    def prompt_entry(self) -> dict:
        return {"id": self.id, "name": self.name, "category": self.category,
                "visual_features": self.visual_features}


@dataclass(frozen=True)
class ManualPage:
    number: int
    text: str


def label_pattern(label: str) -> re.Pattern:
    # "TP-58" also matches "tp58" and "TP 58", but not "TP-580".
    parts = re.findall(r"[^\W_]+", label)
    return re.compile(r"(?<![^\W_])" + r"[\s_-]*".join(map(re.escape, parts)) + r"(?![^\W_])", re.I)


class Catalog:
    def __init__(self, path: Path, products: list[Product]):
        self.path = path
        self.products = {product.id: product for product in products}
        self.patterns = {product.id: [label_pattern(label) for label in (product.name, *product.aliases)]
                         for product in products}

    def get(self, product_id: str | None) -> Product | None:
        return self.products.get(product_id) if product_id else None

    def mentioned(self, text: str) -> list[str]:
        return [pid for pid, patterns in self.patterns.items() if any(p.search(text) for p in patterns)]

    def single_mention(self, *texts: str) -> str | None:
        """Return a product only when the first text mentioning any product names exactly one."""
        for text in texts:
            found = self.mentioned(text)
            if found:
                return found[0] if len(found) == 1 else None
        return None

    def versions(self) -> dict[str, str]:
        """SHA-256 of the catalog and every manual, so index freshness covers all sources."""
        files = [self.path, *(p.manual for p in self.products.values() if p.manual)]
        return {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in files}

    def prompt_json(self) -> str:
        return json.dumps([product.prompt_entry() for product in self.products.values()], ensure_ascii=False)


def text_field(entry: dict, key: str, limit: int) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise CatalogError(f"Catalog field '{key}' must be non-empty text up to {limit} characters.")
    return value.strip()


def load_catalog(path: Path) -> Catalog:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CatalogError("Product catalog is missing or is not valid JSON.") from error
    entries = data.get("products") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_PRODUCTS:
        raise CatalogError(f"Product catalog needs 1-{MAX_PRODUCTS} products.")
    folder = path.parent.resolve()
    products = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != PRODUCT_FIELDS:
            raise CatalogError(f"Each catalog product needs exactly these fields: {sorted(PRODUCT_FIELDS)}.")
        product_id = entry["id"]
        if not isinstance(product_id, str) or not ID_PATTERN.match(product_id):
            raise CatalogError("Catalog product IDs must be lowercase letters, digits, and hyphens.")
        aliases = entry["aliases"]
        if not isinstance(aliases, list) or len(aliases) > 5 or not all(
                isinstance(a, str) and re.search(r"[^\W_]", a) and len(a) <= 40 for a in aliases):
            raise CatalogError("Catalog aliases must be up to five short labels.")
        manual = None
        if entry["manual"] is not None:
            if not isinstance(entry["manual"], str):
                raise CatalogError("Catalog manual must be a file name or null.")
            manual = (folder / entry["manual"]).resolve()
            # Manuals must live beside the catalog: no traversal to other project files.
            if manual.parent != folder or manual.suffix.lower() != ".pdf" or not manual.is_file():
                raise CatalogError(f"Manual for {product_id} must be an existing PDF in the catalog folder.")
        products.append(Product(
            product_id, text_field(entry, "name", 80), text_field(entry, "category", 80),
            tuple(aliases), text_field(entry, "visual_features", 600), manual,
        ))
    if len({p.id for p in products}) != len(products):
        raise CatalogError("Catalog product IDs must be unique.")
    return Catalog(path.resolve(), products)


def clean_cell(value) -> str:
    return " ".join(str(value or "").split()).replace("|", "/")


def table_markdown(rows: list[list]) -> str:
    lines = ["| " + " | ".join(clean_cell(cell) for cell in row) + " |" for row in rows if any(row)]
    if len(lines) > 1:
        lines.insert(1, "|" + " --- |" * len(rows[0]))
    return "\n".join(lines)


def page_text(page) -> str:
    """Text in reading order, with ruled tables replaced by Markdown rows (no duplicated cell text)."""
    tables = sorted(page.find_tables(), key=lambda table: table.bbox[1])
    pieces = []
    top = 0
    for table in tables:
        above = page.within_bbox((0, top, page.width, max(top, table.bbox[1]))).extract_text()
        pieces += [above, table_markdown(table.extract())]
        top = table.bbox[3]
    pieces.append(page.within_bbox((0, min(top, page.height), page.width, page.height)).extract_text())
    return "\n".join(piece.strip() for piece in pieces if piece and piece.strip())


def extract_pages(path: Path) -> tuple[list[ManualPage], list[int]]:
    """Return readable pages and the page numbers without a text layer (scans need OCR)."""
    if path.stat().st_size > MAX_MANUAL_BYTES:
        raise CatalogError(f"{path.name} exceeds {MAX_MANUAL_BYTES // 1024 // 1024} MB.")
    try:
        with pdfplumber.open(path) as pdf:
            if len(pdf.pages) > MAX_MANUAL_PAGES:
                raise CatalogError(f"{path.name} exceeds {MAX_MANUAL_PAGES} pages.")
            pages, unreadable = [], []
            for page in pdf.pages:
                text = page_text(page)
                if text:
                    pages.append(ManualPage(page.page_number, text))
                else:
                    unreadable.append(page.page_number)
    except CatalogError:
        raise
    except Exception as error:  # pdfminer raises many parser-specific exception types.
        raise CatalogError(f"{path.name} could not be read as a PDF.") from error
    if not pages:
        raise CatalogError(f"{path.name} has no extractable text. Scanned manuals need OCR, which is not enabled.")
    return pages, unreadable
