"""Synthetic raster rendering and pixel checks; never used to produce worker claims."""
from dataclasses import dataclass
from io import BytesIO
from PIL import Image, ImageDraw

# Coordinates are relative to the 60 x 90 signal ROI. Seven-segment glyph.
SEGMENTS = ((10, 4, 50, 12), (46, 10, 54, 43), (46, 47, 54, 80),
            (10, 78, 50, 86), (6, 47, 14, 80), (6, 10, 14, 43), (10, 41, 50, 49))
ACTIVE = {0: {0, 1, 2, 3, 4, 5}, 1: {1, 2}}
SIGNAL_ROI = (130, 60, 190, 150)
MOCK_LABEL = 'MOCK / SYNTHETIC - NO VISION MODEL'


@dataclass(frozen=True)
class Raster:
    payload: bytes
    modality: str
    roi: tuple[float, float, float, float]


def encode(image, fmt='PNG', **options):
    buffer = BytesIO()
    image.save(buffer, format=fmt, **options)
    return buffer.getvalue()


def decode(payload):
    with Image.open(BytesIO(payload)) as image:
        image.load()
        return image.convert('RGB')


def render(value, style=0):
    if type(value) is not int or value not in ACTIVE:
        raise ValueError('binary fixture reading required')
    # Style is a nuisance rendering parameter, independent of observation identity.
    image = Image.new('RGB', (320, 180), (240-style*3, 245-style*2, 249))
    draw = ImageDraw.Draw(image)
    draw.rectangle((4, 4, 315, 175), outline=(50+style*15, 80, 110), width=2+style)
    draw.text((12, 12), 'MOCK SYNTHETIC SENSOR', fill=(20, 30, 45))
    draw.text((12, 162), 'FIXTURE READING / NO VISION MODEL', fill=(20, 30, 45))
    draw.rectangle((115, 48, 205, 155), fill=(20, 65, 80))
    for i in ACTIVE[value]:
        x0, y0, x1, y1 = SEGMENTS[i]
        draw.rectangle((130+x0, 60+y0, 130+x1, 60+y1), fill=(250, 250, 250))
    return Raster(encode(image), 'image/png', SIGNAL_ROI)


def resize(source, size):
    image = decode(source.payload)
    w, h = image.size
    if len(size) != 2 or min(size) < 1:
        raise ValueError('invalid target size')
    result = image.resize(tuple(size), Image.Resampling.LANCZOS)
    x0, y0, x1, y1 = source.roi
    return Raster(encode(result), 'image/png', (x0*size[0]/w, y0*size[1]/h, x1*size[0]/w, y1*size[1]/h))


def compress(source, quality):
    if not 1 <= quality <= 95:
        raise ValueError('JPEG quality must be 1..95')
    return Raster(encode(decode(source.payload), 'JPEG', quality=quality, subsampling=0, optimize=False), 'image/jpeg', source.roi)


def crop(source, box):
    image = decode(source.payload)
    left, top, right, bottom = box
    x0, y0, x1, y1 = source.roi
    if not (0 <= left <= x0 < x1 <= right <= image.width and 0 <= top <= y0 < y1 <= bottom <= image.height):
        raise ValueError('crop must retain the entire signal ROI and remain in bounds')
    return Raster(encode(image.crop(tuple(box))), 'image/png', (x0-left, y0-top, x1-left, y1-top))


def signal_check(source, expected):
    """Evaluator-only known-geometry check of all seven segment centers.

    Requires minimum native ROI size and expected foreground/background contrast.
    Does not feed a reading back into any worker. Not general OCR/readability proof.
    """
    if expected not in ACTIVE:
        raise ValueError('unknown expected glyph')
    image = decode(source.payload)
    x0, y0, x1, y1 = source.roi
    bounds_ok = 0 <= x0 < x1 <= image.width and 0 <= y0 < y1 <= image.height
    size_ok = x1-x0 >= 24 and y1-y0 >= 36
    if not bounds_ok:
        return {'passed': False, 'reason': 'ROI out of bounds'}
    gray = image.convert('L')
    measurements = []
    for i, (a,b,c,d) in enumerate(SEGMENTS):
        cx, cy = x0 + (a+c)/2/60*(x1-x0), y0 + (b+d)/2/90*(y1-y0)
        patch = gray.crop((int(cx)-1, int(cy)-1, int(cx)+2, int(cy)+2))
        intensity = sum(patch.get_flattened_data()) / 9
        active = i in ACTIVE[expected]
        measurements.append({'segment': i, 'expected_active': active, 'mean_luminance': intensity,
                             'passed': intensity >= 190 if active else intensity <= 110})
    return {'passed': bool(size_ok and all(m['passed'] for m in measurements)),
            'roi': list(source.roi), 'image_size': list(image.size), 'minimum_size_passed': size_ok,
            'segments': measurements}


def contact_sheet(path, rows, description="Each row follows one acquisition across transformations."):
    """rows: (label, [(column label, Raster), ...]); labels are outside image crops."""
    columns = max(len(images) for _, images in rows)
    label_width = max(100, max(len(label) for label, _ in rows)*7+20)
    sheet = Image.new('RGB', (columns*210+label_width, len(rows)*150+70), 'white')
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 12), MOCK_LABEL + ' | SIGNAL-PRESERVATION INSPECTION', fill='black')
    draw.text((12, 32), description, fill='black')
    for i, (label, images) in enumerate(rows):
        y = 70+i*150
        draw.text((5, y+30), label, fill='black')
        for j, (name, raster) in enumerate(images):
            x = label_width+j*210
            draw.text((x, y), name, fill='black')
            image = decode(raster.payload)
            image.thumbnail((196, 115), Image.Resampling.LANCZOS)
            sheet.paste(image, (x, y+22))
    sheet.save(path)
