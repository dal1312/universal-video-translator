from __future__ import annotations

from PIL import Image, ImageDraw


BRAND_BLUE = "#315ef5"


def create_icon(size: int = 64) -> Image.Image:
    """Render the UVT video-and-subtitles mark at the requested size."""
    if size < 16:
        raise ValueError("La dimensione minima dell'icona è 16 pixel.")
    scale = 4
    canvas_size = size * scale
    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    margin = round(canvas_size * 0.06)
    radius = round(canvas_size * 0.22)
    draw.rounded_rectangle(
        (margin, margin, canvas_size - margin, canvas_size - margin),
        radius=radius,
        fill=BRAND_BLUE,
    )
    draw.polygon(
        (
            (round(canvas_size * 0.35), round(canvas_size * 0.22)),
            (round(canvas_size * 0.70), round(canvas_size * 0.43)),
            (round(canvas_size * 0.35), round(canvas_size * 0.64)),
        ),
        fill="white",
    )
    line_width = max(scale, round(canvas_size * 0.055))
    draw.rounded_rectangle(
        (
            round(canvas_size * 0.23),
            round(canvas_size * 0.73),
            round(canvas_size * 0.77),
            round(canvas_size * 0.73) + line_width,
        ),
        radius=line_width // 2,
        fill="white",
    )
    draw.rounded_rectangle(
        (
            round(canvas_size * 0.31),
            round(canvas_size * 0.83),
            round(canvas_size * 0.69),
            round(canvas_size * 0.83) + line_width,
        ),
        radius=line_width // 2,
        fill="white",
    )
    return image.resize((size, size), Image.Resampling.LANCZOS)
