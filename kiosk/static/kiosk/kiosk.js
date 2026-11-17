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

  // Quantity stepper (R5): big minus and plus; the button label follows the number.
  root.querySelectorAll("form").forEach((form) => {
    const qty = form.querySelector("[data-qty]");
    const label = form.querySelector("[data-qty-label]");
    if (!qty) return;
    const sync = () => { if (label) label.textContent = qty.value || "0"; };
    form.querySelectorAll("[data-step]").forEach((button) => {
      button.addEventListener("click", () => {
        const next = (parseFloat(qty.value) || 0) + Number(button.dataset.step);
        qty.value = String(Math.max(1, Math.round(next * 1000) / 1000));
        sync();
      });
    });
    qty.addEventListener("input", sync);
  });

  // PIN pad (R11): taps fill the field, dots show progress; a real keyboard still works.
  root.querySelectorAll("[data-pin-form]").forEach((form) => {
    const pin = form.querySelector("[data-pin]");
    const dots = form.querySelector("[data-dots]");
    const draw = () => {
      dots.innerHTML = "<span></span>".repeat(Math.max(4, pin.value.length));
      [...dots.children].forEach((dot, i) => dot.classList.toggle("on", i < pin.value.length));
    };
    form.querySelectorAll("[data-digit]").forEach((key) => key.addEventListener("click", () => {
      if (pin.value.length < 6) pin.value += key.dataset.digit;
      draw();
    }));
    form.querySelector("[data-back]").addEventListener("click", () => { pin.value = pin.value.slice(0, -1); draw(); });
    form.querySelector("[data-clear]").addEventListener("click", () => { pin.value = ""; draw(); });
    pin.addEventListener("input", draw);
    draw();
  });

  // Name search on the tablet (R8): filter as you type.
  root.querySelectorAll("[data-filter]").forEach((input) => {
    const rows = [...root.querySelectorAll(".rows a[data-name]")];
    const empty = root.querySelector("[data-filter-empty]");
    input.addEventListener("input", () => {
      const term = input.value.trim().toLowerCase();
      let shown = 0;
      rows.forEach((row) => {
        row.hidden = term !== "" && !row.dataset.name.includes(term);
        if (!row.hidden) shown += 1;
      });
      if (empty) empty.hidden = shown > 0;
    });
  });
}

// Busy state within 400 ms (R1, Doherty threshold): the pressed button says so and can't be
// pressed again until the answer arrives.
document.addEventListener("htmx:beforeRequest", (event) => {
  const button = event.detail.requestConfig?.triggeringEvent?.submitter;
  if (!button) return;
  button.dataset.label = button.innerHTML;
  button.setAttribute("aria-busy", "true");
  button.textContent = "Saving...";
});
document.addEventListener("htmx:afterRequest", (event) => {
  const button = event.detail.requestConfig?.triggeringEvent?.submitter;
  if (!button || !button.isConnected || button.dataset.label === undefined) return;
  button.innerHTML = button.dataset.label;
  button.removeAttribute("aria-busy");
});

if (window.htmx) {
  htmx.onLoad(init); // runs for the first page and for every boosted page swap
} else {
  init(document);
}

// Online only (ADR 0033). If a request never gets an answer we can't know whether the server
// saved it, but the form still holds the same request key, so pressing again is safe (ADR 0007).
function showNoConnection() {
  if (document.getElementById("no-connection")) return;
  const box = document.createElement("p");
  box.id = "no-connection";
  box.className = "error";
  box.setAttribute("role", "alert");
  box.textContent =
    "No connection. Check the WiFi and press the button again; it will not be recorded twice.";
  document.querySelector("main")?.prepend(box);
}
document.addEventListener("htmx:sendError", showNoConnection);
document.addEventListener("htmx:timeout", showNoConnection);
document.addEventListener("htmx:beforeRequest", () => {
  document.getElementById("no-connection")?.remove();
});
