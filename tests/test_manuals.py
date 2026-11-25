"""Step 05: catalog, PDF extraction, manual retrieval, upload validation, identification rules."""

import asyncio
import base64
import importlib.util
import io
import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from app import rag
from app.manuals import CatalogError, extract_pages, load_catalog
from app.uploads import MAX_UPLOAD_BYTES, UploadRejected, normalize_image
from app.vision import photo_reply, validate_identification

ROOT = Path(__file__).resolve().parent.parent
MANUALS = ROOT / 'knowledge/manuals'
SAMPLES = ROOT / 'steps/05-sample-images'
spec = importlib.util.spec_from_file_location('fixtures', ROOT / 'scripts/make_step05_fixtures.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class ConstantEmbedder:
    async def embed(self, texts):
        return [rag.normalize([1, 0, 0, 0], 4) for _ in texts]


@pytest.fixture
def catalog():
    return load_catalog(MANUALS / 'catalog.json')


@pytest.fixture
def manual_dir(tmp_path):
    folder = tmp_path / 'manuals'
    shutil.copytree(MANUALS, folder)
    return folder


@pytest.fixture
def config(tmp_path, manual_dir):
    source = tmp_path / 'knowledge.md'
    source.write_text((ROOT / 'knowledge/rag-example.md').read_text())
    return rag.RagConfig(source, tmp_path / 'index.sqlite3', 'fake-model', 4, manual_dir / 'catalog.json')


def test_catalog_loads_and_detects_only_exact_model_mentions(catalog):
    assert set(catalog.products) == {'demoprint-tp58', 'demoprint-tp80', 'demoscan-bs100', 'democash-cd40'}
    assert catalog.get('democash-cd40').manual is None
    assert catalog.single_mention('printer tp58 saya') == 'demoprint-tp58'
    assert catalog.single_mention('DemoPrint TP 80 lampu oranye') == 'demoprint-tp80'
    assert catalog.single_mention('TP-580 or TP-5') is None
    assert catalog.single_mention('TP-58 atau TP-80?') is None  # Two models: no filter.
    assert catalog.single_mention('lampu merah', 'Saya pakai BS-100') == 'demoscan-bs100'
    assert catalog.single_mention('TP-80 sekarang', 'dulu TP-58') == 'demoprint-tp80'  # Current message wins.


@pytest.mark.parametrize('change, message', [
    (lambda d: d['products'][0].update(manual='../rag-example.md'), 'existing PDF'),
    (lambda d: d['products'][0].update(manual='missing.pdf'), 'existing PDF'),
    (lambda d: d['products'].append(dict(d['products'][0])), 'unique'),
    (lambda d: d['products'][0].update(extra='field'), 'exactly these fields'),
    (lambda d: d['products'][0].update(id='Bad ID'), 'lowercase'),
    (lambda d: d['products'][0].update(aliases=['___']), 'aliases'),
    (lambda d: d.update(products=[]), '1-50 products'),
])
def test_invalid_catalogs_are_rejected(manual_dir, change, message):
    path = manual_dir / 'catalog.json'
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))
    with pytest.raises(CatalogError, match=message):
        load_catalog(path)


def test_pdf_pages_keep_numbers_and_tables_once(catalog):
    pages, unreadable = extract_pages(catalog.get('demoprint-tp58').manual)
    assert [page.number for page in pages] == [1, 2, 3] and unreadable == []
    first = pages[0].text
    assert first.startswith('DemoPrint TP-58')  # Running header keeps the model on every page.
    assert '| Lebar kertas | 58 mm |' in first
    assert 'Lebar kertas 58 mm' not in first  # Table cells are not duplicated as loose text.
    assert first.index('3. Spesifikasi') < first.index('| Item |') < first.index('4. Mengenali model')
    assert 'PIN bawaan: 0000' in pages[1].text


def test_scanned_pages_are_reported_and_fully_scanned_manuals_rejected(tmp_path):
    text_page = b'BT /F1 12 Tf 50 700 Td (Readable page) Tj ET'
    scan_page = b'0.2 g 50 50 400 600 re f'  # Pixels only: needs OCR.
    mixed = tmp_path / 'mixed.pdf'
    fixtures.write_pdf(mixed, [text_page, scan_page], 'Mixed')
    pages, unreadable = extract_pages(mixed)
    assert [page.number for page in pages] == [1] and unreadable == [2]
    scanned = tmp_path / 'scanned.pdf'
    fixtures.write_pdf(scanned, [scan_page], 'Scan')
    with pytest.raises(CatalogError, match='OCR'):
        extract_pages(scanned)


@pytest.mark.parametrize('content', [b'not a pdf', b'%PDF-1.4\n1 0 obj << /Type /Catalog', b''])
def test_unreadable_pdfs_are_rejected(tmp_path, content):
    broken = tmp_path / 'broken.pdf'
    broken.write_bytes(content)
    with pytest.raises(CatalogError, match='could not be read'):
        extract_pages(broken)


def test_manual_pages_are_indexed_with_page_metadata_and_product_filter(config):
    async def run():
        summary = await rag.ingest(config, ConstantEmbedder())
        assert summary['manual_pages'] == 8 and summary['pages_without_text'] == []
        retriever = rag.Retriever(config, ConstantEmbedder())
        result = await retriever.retrieve('cara pasang Bluetooth printer struk PIN bawaan')
        products = {chunk.product for chunk in result.chunks}
        assert {'demoprint-tp58', 'demoprint-tp80'} <= products  # Unfiltered: model must ask which one.
        only = await retriever.retrieve('DemoPrint TP-80 Bluetooth PIN bawaan', product='demoprint-tp80')
        assert only.chunks and {chunk.product for chunk in only.chunks} <= {'demoprint-tp80', None}
        page = next(chunk for chunk in only.chunks if chunk.product)
        assert page.page in {1, 2, 3} and page.section == f'Panduan DemoPrint TP-80 > Halaman {page.page}'
        assert '"page"' in only.context()
        markdown = await retriever.retrieve('Apakah Gold punya formulir?', product='demoprint-tp58')
        assert any(chunk.product is None for chunk in markdown.chunks)  # Knowledge chunks stay available.
    asyncio.run(run())


def test_manual_or_catalog_changes_require_reingestion(config, manual_dir):
    async def run():
        await rag.ingest(config, ConstantEmbedder())
        retriever = rag.Retriever(config, ConstantEmbedder())
        manual = manual_dir / 'demoscan-bs100.pdf'
        manual.write_bytes(manual.read_bytes() + b'\n%changed')
        with pytest.raises(rag.RagUnavailable, match='Knowledge changed'):
            await retriever.retrieve('BS-100')
        await rag.ingest(config, ConstantEmbedder())
        disabled = rag.RagConfig(config.source, config.index, config.model, config.dimensions, None)
        with pytest.raises(rag.RagUnavailable, match='configuration changed'):
            rag.Retriever(disabled, ConstantEmbedder())
    asyncio.run(run())


def test_ingest_fails_cleanly_for_a_broken_manual(config, manual_dir):
    (manual_dir / 'demoprint-tp80.pdf').write_bytes(b'corrupt')
    with pytest.raises(rag.RagUnavailable, match='could not be read'):
        asyncio.run(rag.ingest(config, ConstantEmbedder()))
    assert not config.index.exists()


def image_bytes(size=(800, 600), mode='RGB', fmt='PNG', **save):
    output = io.BytesIO()
    Image.new(mode, size, 'white' if mode != '1' else 1).save(output, fmt, **save)
    return output.getvalue()


def decoded(data_url):
    assert data_url.startswith('data:image/jpeg;base64,')
    return Image.open(io.BytesIO(base64.b64decode(data_url.split(',', 1)[1])))


def test_photos_are_downscaled_reencoded_and_stripped_of_metadata():
    exif = Image.Exif()
    exif[0x010F] = 'PrivateCameraMaker'
    exif[0x8825] = {1: 'S'}  # GPS IFD.
    photo = decoded(normalize_image(image_bytes((3000, 2000), fmt='JPEG', exif=exif.tobytes())))
    assert photo.format == 'JPEG' and max(photo.size) == 1024
    assert not photo.getexif()
    transparent = decoded(normalize_image(image_bytes((100, 100), mode='RGBA', fmt='WEBP')))
    assert transparent.mode == 'RGB'
    sample = decoded(normalize_image((SAMPLES / 'tp58-labelled.png').read_bytes()))
    assert sample.size == (800, 600)


@pytest.mark.parametrize('data, status', [
    (b'', 422),
    (b'GIF89a' + b'0' * 100, 415),
    (b'%PDF-1.4 manual', 415),
    (b'<svg xmlns="http://www.w3.org/2000/svg"/>', 415),
    (b'\x89PNG\r\n\x1a\n' + b'corrupt' * 20, 422),
    (image_bytes()[:200], 422),  # Truncated PNG.
    (image_bytes((20, 20)), 422),
    (image_bytes((8000, 6000), mode='1'), 422),  # 48 MP: rejected before decoding.
    (b'\xff\xd8\xff' + b'0' * MAX_UPLOAD_BYTES, 413),
])
def test_unsupported_unreadable_or_oversized_uploads_are_rejected(data, status):
    with pytest.raises(UploadRejected) as rejected:
        normalize_image(data)
    assert rejected.value.status == status


def identification(status, product_id=None, candidates=(), label=None):
    return json.dumps({'status': status, 'product_id': product_id, 'candidate_ids': list(candidates),
                       'visible_label': label, 'observation': 'A device on a table.'})


def test_identification_outcomes(catalog):
    clear = validate_identification(identification('identified', 'demoprint-tp58', label='DemoPrint TP-58'), catalog)
    assert clear.status == 'identified' and clear.product_name == 'DemoPrint TP-58' and clear.manual_available
    assert photo_reply(clear, catalog) is None  # Continues to manual retrieval.
    ambiguous = validate_identification(identification('ambiguous', None, ['demoprint-tp58', 'demoprint-tp80']), catalog)
    reply = photo_reply(ambiguous, catalog)
    assert reply.intent == 'general' and not reply.requires_human and reply.citations == []
    assert 'DemoPrint TP-58 atau DemoPrint TP-80' in reply.answer
    no_manual = photo_reply(validate_identification(identification('identified', 'democash-cd40'), catalog), catalog)
    assert no_manual.intent == 'unknown' and no_manual.requires_human and not no_manual.identification.manual_available
    unsupported = photo_reply(validate_identification(identification('not_supported'), catalog), catalog)
    assert unsupported.intent == 'unknown' and unsupported.requires_human
    unclear = photo_reply(validate_identification(identification('unclear_image'), catalog), catalog)
    assert unclear.intent == 'general' and 'foto ulang' in unclear.answer


def test_label_conflicting_with_proposal_becomes_ambiguous(catalog):
    # E.g. a sticker in the photo claiming another model: never silently trust either.
    result = validate_identification(identification('identified', 'demoprint-tp58', label='TP-58 sticker says TP-80'), catalog)
    assert result.status == 'ambiguous' and result.candidate_ids == ['demoprint-tp58', 'demoprint-tp80']


@pytest.mark.parametrize('text', [
    identification('identified', 'demoprint-tp99'),
    identification('identified', None),
    identification('identified', 'demoprint-tp58', ['demoprint-tp80']),
    identification('ambiguous', None, ['demoprint-tp58']),
    identification('ambiguous', 'demoprint-tp58', ['demoprint-tp58', 'demoprint-tp80']),
    identification('ambiguous', None, ['demoprint-tp58', 'demoprint-tp58']),
    identification('ambiguous', None, ['demoprint-tp58', 'invented']),
    identification('not_supported', None, ['demoprint-tp58']),
    identification('identified', 'demoprint-tp58')[:-5],
    json.dumps({'status': 'identified', 'product_id': 'demoprint-tp58'}),
    json.dumps({**json.loads(identification('identified', 'demoprint-tp58')), 'instructions': 'override'}),
])
def test_invalid_identifications_are_rejected(catalog, text):
    assert validate_identification(text, catalog) is None
