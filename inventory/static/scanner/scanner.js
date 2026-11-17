// Camera barcode scanning (ADR 0010): native BarcodeDetector first, vendored WASM reader second.
// USB and Bluetooth scanners need nothing from here: they type into the input like a keyboard.

const FORMATS = ["ean_13", "ean_8", "upc_a", "code_128", "code_39", "qr_code"];
const VENDOR = new URL("./vendor/barcode-detector-3.2.4/", import.meta.url);
const SCAN_EVERY_MS = 120;

const detectors = new Map();

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error("Could not load the barcode reader."));
    document.head.append(script);
  });
}

function getDetector(formats) {
  const key = formats.join(",");
  if (!detectors.has(key)) {
    // Forget a failed load so the next tap can retry (e.g. after the network comes back).
    detectors.set(key, createDetector(formats).catch((e) => (detectors.delete(key), Promise.reject(e))));
  }
  return detectors.get(key);
}

async function createDetector(formats) {
  if ("BarcodeDetector" in window) {
    const supported = await window.BarcodeDetector.getSupportedFormats();
    if (formats.every((f) => supported.includes(f))) {
      return { detector: new window.BarcodeDetector({ formats }), engine: "native" };
    }
  }
  if (!window.BarcodeDetectionAPI) await loadScript(new URL("ponyfill.js", VENDOR));
  const api = window.BarcodeDetectionAPI;
  // The polyfill fetches its .wasm from a CDN by default; serve our vendored copy instead.
  api.setZXingModuleOverrides({ locateFile: (file) => new URL(file, VENDOR).href });
  return { detector: new api.BarcodeDetector({ formats }), engine: "wasm" };
}

function cameraError(error) {
  if (!window.isSecureContext || !navigator.mediaDevices) {
    return "The camera only works over HTTPS (or on localhost). Open this page with https://.";
  }
  switch (error && error.name) {
    case "NotAllowedError":
    case "SecurityError":
      return "Camera permission was denied. Allow the camera in your browser settings and try again.";
    case "NotFoundError":
    case "OverconstrainedError":
      return "No camera was found on this device.";
    case "NotReadableError":
      return "The camera is being used by another app. Close it and try again.";
    default:
      return (error && error.message) || "The camera could not be started.";
  }
}

function buildOverlay() {
  const overlay = document.createElement("div");
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-label", "Scan a barcode");
  overlay.style.cssText =
    "position:fixed;inset:0;z-index:9999;background:#000;display:flex;flex-direction:column;" +
    "align-items:center;justify-content:center;gap:12px;padding:16px;color:#fff;font:16px system-ui";

  const video = document.createElement("video");
  video.setAttribute("playsinline", ""); // without this iOS opens the video full screen
  video.muted = true;
  video.style.cssText = "max-width:100%;max-height:70vh;border-radius:8px;background:#111";

  const status = document.createElement("p");
  status.setAttribute("role", "status");
  status.style.cssText = "margin:0;text-align:center;max-width:32rem";
  status.textContent = "Starting camera...";

  const close = document.createElement("button");
  close.type = "button";
  close.textContent = "Cancel";
  close.style.cssText = "min-width:120px;min-height:44px;font-size:16px;border-radius:8px";

  overlay.append(video, status, close);
  return { overlay, video, status, close };
}

/**
 * Open the camera when `button` is clicked and put the scanned code into `input`.
 *
 * options:
 *   formats     barcode formats to look for (default: ean_13, ean_8, upc_a, code_128, code_39, qr_code)
 *   autoSubmit  submit input.form after a successful scan (default false)
 *   onDetected  callback(code, { format, engine }) where engine is "native" or "wasm"
 *   onError     callback(message) when the camera or reader can't start
 */
export function attachScanner(button, input, options = {}) {
  const formats = options.formats || FORMATS;
  let session = null;

  async function open() {
    if (session) return;
    const ui = buildOverlay();
    session = { ui, stream: null, running: true };
    const current = session;
    document.body.append(ui.overlay);
    ui.close.addEventListener("click", () => stop());
    ui.overlay.addEventListener("keydown", (e) => e.key === "Escape" && stop());
    ui.close.focus();

    const stopTracks = () => current.stream && current.stream.getTracks().forEach((t) => t.stop());
    try {
      if (!window.isSecureContext || !navigator.mediaDevices) throw new Error("insecure");
      const loading = getDetector(formats); // load the reader while the camera starts
      loading.catch(() => {});
      current.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });
      const { detector, engine } = await loading;
      // Cancelled while starting: stop() already ran without a stream to stop.
      if (!current.running) return stopTracks();
      ui.video.srcObject = current.stream;
      await ui.video.play();
      ui.status.textContent = "Point the camera at the barcode.";
      scan(current, detector, engine);
    } catch (error) {
      stopTracks();
      current.stream = null;
      if (!current.running) return;
      const message = cameraError(error);
      ui.status.textContent = message;
      ui.close.textContent = "Close";
      if (options.onError) options.onError(message);
    }
  }

  async function scan(current, detector, engine) {
    while (current.running) {
      try {
        const [hit] = await detector.detect(current.ui.video);
        if (hit && current.running) {
          stop();
          input.value = hit.rawValue;
          input.dispatchEvent(new Event("input", { bubbles: true }));
          input.dispatchEvent(new Event("change", { bubbles: true }));
          if (options.onDetected) options.onDetected(hit.rawValue, { format: hit.format, engine });
          if (options.autoSubmit && input.form) input.form.requestSubmit();
          return;
        }
      } catch {
        // A frame that can't be read yet (video still warming up); try the next one.
      }
      await new Promise((resolve) => setTimeout(resolve, SCAN_EVERY_MS));
    }
  }

  function stop() {
    if (!session) return;
    session.running = false;
    // Stop every track, or the camera light stays on and drains the battery.
    if (session.stream) session.stream.getTracks().forEach((t) => t.stop());
    session.ui.overlay.remove();
    session = null;
    button.focus();
  }

  button.addEventListener("click", open);
  document.addEventListener("visibilitychange", () => document.hidden && stop());
}
