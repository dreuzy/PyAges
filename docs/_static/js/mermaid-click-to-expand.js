(() => {
  "use strict";

  const diagramSelector = ".mermaid-container > pre.mermaid";
  const movementThreshold = 6;

  function openFullscreen(diagram) {
    if (diagram.closest(".mermaid-fullscreen-modal")) {
      return;
    }

    const container = diagram.closest(".mermaid-container");
    const button = container?.querySelector(".mermaid-fullscreen-btn");
    button?.click();
  }

  function prepareDiagram(diagram) {
    if (
      diagram.dataset.clickToExpand === "true" ||
      diagram.closest(".mermaid-fullscreen-modal")
    ) {
      return;
    }

    diagram.dataset.clickToExpand = "true";
    diagram.tabIndex = 0;
    diagram.setAttribute("role", "button");
    diagram.setAttribute("aria-label", "Open diagram in full-screen view");
    diagram.title = "Click to enlarge";

    const container = diagram.closest(".mermaid-container");
    if (container && !container.querySelector(".mermaid-expand-hint")) {
      const hint = document.createElement("span");
      hint.className = "mermaid-expand-hint";
      hint.textContent = "Click diagram to enlarge";
      container.appendChild(hint);
    }

    let pointerStart = null;
    let pointerMoved = false;

    diagram.addEventListener(
      "pointerdown",
      (event) => {
        pointerStart = { x: event.clientX, y: event.clientY };
        pointerMoved = false;
      },
      true,
    );

    diagram.addEventListener(
      "pointermove",
      (event) => {
        if (!pointerStart) {
          return;
        }
        const distance = Math.hypot(
          event.clientX - pointerStart.x,
          event.clientY - pointerStart.y,
        );
        if (distance > movementThreshold) {
          pointerMoved = true;
        }
      },
      true,
    );

    diagram.addEventListener(
      "pointercancel",
      () => {
        pointerStart = null;
        pointerMoved = false;
      },
      true,
    );

    diagram.addEventListener(
      "click",
      (event) => {
        pointerStart = null;
        if (pointerMoved) {
          pointerMoved = false;
          return;
        }
        if (event.target.closest(".mermaid-fullscreen-btn")) {
          return;
        }
        openFullscreen(diagram);
      },
      true,
    );

    diagram.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      event.preventDefault();
      openFullscreen(diagram);
    });
  }

  function prepareAllDiagrams() {
    document.querySelectorAll(diagramSelector).forEach(prepareDiagram);
  }

  const observer = new MutationObserver(prepareAllDiagrams);

  function start() {
    prepareAllDiagrams();
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
