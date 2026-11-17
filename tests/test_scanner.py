import hashlib
import re
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.views import serve
from django.test import RequestFactory

VENDOR = "scanner/vendor/barcode-detector-3.2.4"


def static_text(path):
    return Path(finders.find(path)).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "path",
    [
        "scanner/scanner.js",
        "scanner/demo.html",
        f"{VENDOR}/ponyfill.js",
        f"{VENDOR}/zxing_reader.wasm",
        f"{VENDOR}/LICENSE-barcode-detector",
        f"{VENDOR}/LICENSE-zxing-wasm",
        f"{VENDOR}/LICENSE-zxing-cpp",
    ],
)
def test_scanner_files_are_static_files(path):
    assert finders.find(path)


def test_module_exports_the_phase_5_api():
    assert "export function attachScanner(button, input, options = {})" in static_text(
        "scanner/scanner.js"
    )


def test_vendored_wasm_is_the_one_the_polyfill_was_built_for():
    # The polyfill embeds the SHA-256 of the wasm it expects; a mismatched upgrade fails here.
    polyfill = static_text(f"{VENDOR}/ponyfill.js")
    variable = re.search(r"ZXING_WASM_SHA256=(\w+)", polyfill).group(1)
    expected = re.search(rf"\b{variable}=`([0-9a-f]{{64}})`", polyfill).group(1)
    wasm = Path(finders.find(f"{VENDOR}/zxing_reader.wasm")).read_bytes()
    assert hashlib.sha256(wasm).hexdigest() == expected


def test_wasm_is_loaded_locally_not_from_a_cdn():
    module = static_text("scanner/scanner.js")
    assert "setZXingModuleOverrides" in module and "locateFile" in module
    for page in ("scanner/scanner.js", "scanner/demo.html"):
        assert not re.search(r"https?://\w", static_text(page)), f"{page} loads from the internet"


def test_wasm_is_served_with_the_wasm_content_type():
    # Browsers refuse to stream-compile WebAssembly served as anything else.
    response = serve(RequestFactory().get("/"), f"{VENDOR}/zxing_reader.wasm", insecure=True)
    assert response["Content-Type"] == "application/wasm"


def test_module_is_served_as_javascript():
    response = serve(RequestFactory().get("/"), "scanner/scanner.js", insecure=True)
    assert response["Content-Type"].startswith("text/javascript")
