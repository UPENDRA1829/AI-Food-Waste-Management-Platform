import io

import barcode
import qrcode
from barcode.writer import ImageWriter


def generate_barcode_image(code_value: str) -> bytes:
    """Render a Code 128 barcode image for the supplied code value."""
    barcode_class = barcode.get_barcode_class("code128")
    buffer = io.BytesIO()
    barcode_instance = barcode_class(code_value, writer=ImageWriter())
    barcode_instance.write(buffer)
    return buffer.getvalue()


def generate_qr_image(code_value: str) -> bytes:
    """Render a QR code image for the supplied code value."""
    image = qrcode.make(code_value)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_codes(inventory_id: int) -> dict:
    """Generate default internal code values and their PNG images."""
    code_value = f"FOOD{inventory_id:08d}"
    return {
        "barcode": code_value,
        "qr_code": code_value,
        "barcode_image": generate_barcode_image(code_value),
        "qr_image": generate_qr_image(code_value),
    }
