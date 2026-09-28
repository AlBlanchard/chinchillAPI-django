"use strict";
document.querySelectorAll("[data-copy]").forEach((button) => {
  const originalLabel = button.textContent;
  button.addEventListener("click", async () => {
    const status = document.getElementById("copy-status");
    try {
      await navigator.clipboard.writeText(button.dataset.copy);
      status.textContent = "Copié : " + button.dataset.copy;
      button.textContent = "Copié";
      window.setTimeout(() => { button.textContent = originalLabel; }, 2000);
    } catch {
      const input = document.getElementById(button.dataset.copyTarget);
      input.focus();
      input.select();
      status.textContent = "Copie automatique indisponible. Le texte est sélectionné : utilisez Copier.";
    }
  });
});

// Ouvrir un formulaire replié lorsqu'on suit un lien de navigation interne.
document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener("click", () => {
    const target = document.getElementById(link.getAttribute("href").slice(1));
    if (target && target.tagName === "DETAILS") target.open = true;
  });
});
