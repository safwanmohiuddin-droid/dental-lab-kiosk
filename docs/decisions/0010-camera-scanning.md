# 0010. Camera scanning: native API + WASM fallback

- Status: Accepted (owner, 2026-11-16)
- Date: 2026-11-16

## Context
Owner wants phone camera scanning. Chrome on Android has `BarcodeDetector`; iOS Safari does not.
Camera access (`getUserMedia`) only works in a secure context (HTTPS or localhost).

## Decision
Use `BarcodeDetector` when present, else a vendored WASM polyfill (`barcode-detector` package,
zxing-wasm based) served as a static file, no build step, no CDN at runtime. USB/Bluetooth
scanners keep working as keyboard input; the same text field accepts both.
Dev on a phone over LAN uses HTTPS via Caddy's local CA.

## Alternatives considered
- html5-qrcode / quagga: heavier, less maintained.
- Hardware scanners only: cost and setup barrier for small labs.

## Consequences
~1 MB WASM on first scan (cached by the service worker). Must test on a real iPhone.

## Interview angle
"Progressive enhancement: native API first, polyfill second, keyboard-wedge scanner always."
