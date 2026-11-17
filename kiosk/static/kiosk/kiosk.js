// Kiosk page behaviour: request keys made in the browser (ADR 0007) and the optional camera button.

function init(root) {
  // crypto.randomUUID only exists in secure contexts (HTTPS or localhost); on plain HTTP the
  // key the server rendered stays, which is just as safe against double taps.
  if (window.crypto && crypto.randomUUID) {
    root.querySelectorAll("input[data-client-key]").forEach((input) => {
      input.value = crypto.randomUUID();
    });
  }
  // A <meta refresh> inside a boosted page swap is ignored by browsers, so do it here.
  root.querySelectorAll("a[data-go-after]").forEach((link) => {
    setTimeout(() => location.assign(link.href), Number(link.dataset.goAfter) * 1000);
  });
  root.querySelectorAll("[data-scan-for]").forEach(async (button) => {
    const input = document.getElementById(button.dataset.scanFor);
    try {
      const { attachScanner } = await import(button.dataset.scannerUrl);
      attachScanner(button, input, { autoSubmit: true });
      button.hidden = false;
    } catch {
      button.hidden = true; // no camera component installed: scanners and typing still work
    }
  });
}

if (window.htmx) {
  htmx.onLoad(init); // runs for the first page and for every boosted page swap
} else {
  init(document);
}
