import base64
import io
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

# Add backend dir to sys.path so we can import from main
sys.path.insert(0, str(Path(__file__).parent.parent))

# Stub out heavy optional dependencies that may not be installed in test env
_STUBS = ["fitz"]
for _mod in _STUBS:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# Stub service modules
for _svc in [
    "services",
    "services.claude_service",
    "services.history_service",
    "services.hwpx_service",
    "services.gemini_service",
]:
    if _svc not in sys.modules:
        sys.modules[_svc] = MagicMock()

from main import _crop_image  # noqa: E402


def make_img_b64(color: tuple, size: tuple = (100, 100)) -> tuple:
    """Create a solid-color PIL image and return (base64_str, media_type)."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return b64, "image/png"


def decode_img(b64: str) -> Image.Image:
    """Decode a base64 PNG string to a PIL Image."""
    return Image.open(io.BytesIO(base64.b64decode(b64)))


class TestCropImageNormal:
    def test_crop_size_and_pixel(self):
        """Normal crop: 200x200 white image with red pixel at (100,100).
        Crop bbox (x=0.25, y=0.25, w=0.5, h=0.5) -> 100x100 result.
        The red pixel that was at (100,100) should appear at (50,50) in crop.
        """
        # Create 200x200 white image
        img = Image.new("RGB", (200, 200), color=(255, 255, 255))
        # Place a red pixel at (100, 100)
        img.putpixel((100, 100), (255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        result_b64, media_type = _crop_image(b64, "image/png", x=0.25, y=0.25, w=0.5, h=0.5)

        result_img = decode_img(result_b64)
        assert media_type == "image/png"
        assert result_img.size == (100, 100)

        # Original (100, 100) -> left=50, top=50 -> crop-relative (50, 50)
        r, g, b = result_img.getpixel((50, 50))
        assert r == 255 and g == 0 and b == 0, f"Expected red pixel at (50,50), got ({r},{g},{b})"


class TestCropImageClipping:
    def test_bbox_clipped_to_bounds(self):
        """Clipping: 100x100 solid blue image.
        Crop bbox (x=0.8, y=0.8, w=0.5, h=0.5) exceeds 1.0 -> clipped.
        Result should be non-empty and smaller than 50x50 px.
        """
        b64, media_type = make_img_b64(color=(0, 0, 255), size=(100, 100))

        result_b64, result_media_type = _crop_image(b64, media_type, x=0.8, y=0.8, w=0.5, h=0.5)

        result_img = decode_img(result_b64)
        assert result_media_type == "image/png"
        w, h = result_img.size
        # Clipped: right = min(100, int((0.8+0.5)*100)) = min(100,130) = 100
        #           left = int(0.8*100) = 80 -> width = 20
        # Similarly height = 20
        assert w > 0 and h > 0, "Cropped image must be non-empty"
        assert w < 50 and h < 50, f"Expected clipped size < 50x50, got {w}x{h}"


class TestCropImageEmptyBbox:
    def test_zero_wh_raises_value_error(self):
        """Empty crop: bbox with w=0.0, h=0.0 should raise ValueError."""
        b64, media_type = make_img_b64(color=(128, 128, 128), size=(100, 100))

        with pytest.raises(ValueError, match="(?i)invalid bbox|empty crop"):
            _crop_image(b64, media_type, x=0.5, y=0.5, w=0.0, h=0.0)
