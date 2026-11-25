"""Product identification from a photo: a model proposal validated against the catalog."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from app.manuals import Catalog
from app.schemas import PhotoChatResponse, ProductIdentification

MAX_CANDIDATES = 4


class IdentificationOutput(BaseModel):
    """What the vision model may return. Everything here is untrusted until validated."""
    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["identified", "ambiguous", "not_supported", "unclear_image"]
    product_id: str | None
    candidate_ids: Annotated[list[str], Field(max_length=MAX_CANDIDATES)]
    visible_label: Annotated[str, StringConstraints(max_length=120)] | None
    observation: Annotated[str, StringConstraints(max_length=400)]


IDENTIFICATION_SCHEMA = IdentificationOutput.model_json_schema()
IDENTIFICATION_SCHEMA["required"] = list(IDENTIFICATION_SCHEMA["properties"])


def make_identification(catalog: Catalog, status: str, product_id: str | None, candidates: list[str]) -> ProductIdentification:
    product = catalog.get(product_id)
    return ProductIdentification(
        status=status, product_id=product_id, product_name=product.name if product else None,
        candidate_ids=candidates, candidate_names=[catalog.products[cid].name for cid in candidates],
        manual_available=bool(product and product.manual),
    )


def validate_identification(text: str, catalog: Catalog) -> ProductIdentification | None:
    """Return a checked identification, or None when the model output breaks the contract."""
    try:
        output = IdentificationOutput.model_validate_json(text)
    except ValidationError:
        return None
    known = catalog.products
    candidates = list(dict.fromkeys(output.candidate_ids))
    if any(cid not in known for cid in candidates) or len(candidates) != len(output.candidate_ids):
        return None
    if output.status == "identified":
        if output.product_id not in known or set(candidates) - {output.product_id}:
            return None
        # A visible label naming a different catalog model contradicts the proposal: ask instead.
        conflicting = [pid for pid in catalog.mentioned(output.visible_label or "") if pid != output.product_id]
        if conflicting:
            return make_identification(catalog, "ambiguous", None, [output.product_id, *conflicting])
        return make_identification(catalog, "identified", output.product_id, [])
    if output.product_id is not None:
        return None
    if output.status == "ambiguous":
        return make_identification(catalog, "ambiguous", None, candidates) if len(candidates) >= 2 else None
    return None if candidates else make_identification(catalog, output.status, None, [])


def photo_reply(identification: ProductIdentification, catalog: Catalog) -> PhotoChatResponse | None:
    """Fixed replies for every outcome except a confident match with a manual."""
    names = ", ".join(product.name for product in catalog.products.values())
    if identification.status == "identified" and identification.manual_available:
        return None
    if identification.status == "identified":
        answer = (f"Foto ini tampaknya {identification.product_name}. Panduan untuk produk ini belum tersedia, "
                  "jadi saya tidak bisa memberi instruksi khusus model. Silakan hubungi dukungan manusia. "
                  "Belum ada tindakan yang dilakukan.")
        intent, human = "unknown", True
    elif identification.status == "ambiguous":
        options = " atau ".join(identification.candidate_names)
        answer = (f"Saya belum bisa memastikan modelnya: kemungkinan {options}. Instruksinya berbeda antar model, "
                  "jadi saya belum memberi langkah khusus. Kirim foto label model yang jelas, atau ketik nomor "
                  "model yang tertulis di label.")
        intent, human = "general", False
    elif identification.status == "unclear_image":
        answer = ("Fotonya kurang jelas untuk mengenali produk. Coba foto ulang di tempat terang dengan label "
                  "model terlihat, atau ketik nomor modelnya.")
        intent, human = "general", False
    else:
        answer = (f"Saya tidak menemukan produk yang didukung di foto ini. Produk yang didukung: {names}. "
                  "Jika ini perangkat lain, silakan hubungi dukungan manusia.")
        intent, human = "unknown", True
    return PhotoChatResponse(intent=intent, answer=answer, requires_human=human, identification=identification)
