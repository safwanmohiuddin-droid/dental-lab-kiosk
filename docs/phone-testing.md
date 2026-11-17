# Testing the camera scanner on a real phone

Browsers only open the camera in a **secure context**: `https://`, or `http://localhost`.
`http://192.168.x.x:8000` from a phone is *not* secure, so the camera is blocked there
(the scanner says so instead of failing silently).

Demo page: `/static/scanner/demo.html` (served by `runserver` while `DEBUG=True`). It shows
whether the page is a secure context, whether the browser has a native `BarcodeDetector`, and
logs every read with the engine used (`native` or `wasm`).

## Android: USB port forwarding (no certificates)

1. On the phone: enable Developer options and USB debugging; connect it by USB.
2. On the PC in Chrome or Edge: open `chrome://inspect/#devices` (`edge://inspect/#devices`),
   tick **Port forwarding**, add `8000` -> `localhost:8000`.
3. Run `uv run python manage.py runserver`.
4. On the phone open `http://localhost:8000/static/scanner/demo.html`. It counts as secure.

## iPhone or Android over Wi-Fi: HTTPS with Caddy

1. Install [Caddy](https://caddyserver.com/docs/install) on the PC.
2. Find the PC's LAN IP (`ipconfig`), for example `192.168.1.20`.
3. Add it to `ALLOWED_HOSTS` in `.env`, then run `uv run python manage.py runserver 0.0.0.0:8000`.
4. In another terminal: `caddy reverse-proxy --from 192.168.1.20:8443 --to localhost:8000`.
   Caddy creates its own local certificate authority on first run.
5. Trust that authority on the phone. Its root certificate is `root.crt` in Caddy's data
   folder (`%AppData%\Caddy\pki\authorities\local\` on Windows). Send it to the phone, install
   it, and on iPhone also enable it under Settings > General > About > Certificate Trust Settings.
6. On the phone open `https://192.168.1.20:8443/static/scanner/demo.html`.

## What was verified without a phone

Headless Edge on Windows (no native `BarcodeDetector`, so the WASM path) with a fake camera fed
by a generated Code 128 video: the code was read, the overlay closed, the camera stopped and the
form auto-submitted. With camera permission denied, the "permission was denied" message showed.
