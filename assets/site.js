const menuButton = document.querySelector(".menu-button");
const navLinks = document.querySelector(".nav-links");
const themeSelect = document.querySelector("#theme-select");

if (menuButton && navLinks) {
  menuButton.addEventListener("click", () => {
    const expanded = menuButton.getAttribute("aria-expanded") === "true";
    menuButton.setAttribute("aria-expanded", String(!expanded));
    navLinks.classList.toggle("open", !expanded);
  });

  navLinks.addEventListener("click", (event) => {
    if (event.target.closest("a")) {
      menuButton.setAttribute("aria-expanded", "false");
      navLinks.classList.remove("open");
    }
  });
}

if (themeSelect) {
  themeSelect.value = window.quasarTheme || document.documentElement.dataset.theme || "obsidian";
  themeSelect.addEventListener("change", () => {
    document.documentElement.dataset.theme = themeSelect.value;
    try {
      sessionStorage.setItem("quasar-theme", themeSelect.value);
    } catch {
      // Theme switching still works for the current page without storage.
    }
  });
}

document.querySelectorAll("[data-year]").forEach((element) => {
  element.textContent = new Date().getFullYear();
});
