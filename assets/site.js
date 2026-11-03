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

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && menuButton.getAttribute("aria-expanded") === "true") {
      menuButton.setAttribute("aria-expanded", "false");
      navLinks.classList.remove("open");
      menuButton.focus();
    }
  });

  document.documentElement.classList.add("nav-ready");
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

document.documentElement.classList.add("enhanced");

const progress = document.createElement("div");
progress.className = "scroll-progress";
progress.setAttribute("aria-hidden", "true");
document.body.append(progress);

const updateProgress = () => {
  const scrollable = document.documentElement.scrollHeight - window.innerHeight;
  const value = scrollable > 0 ? Math.min(window.scrollY / scrollable, 1) : 0;
  progress.style.setProperty("--scroll-progress", String(value));
};

updateProgress();
window.addEventListener("scroll", updateProgress, { passive: true });
window.addEventListener("resize", updateProgress);

const revealItems = document.querySelectorAll(
  ".section-heading, .project-card, .status-row, .precision-item, .detail-grid article, .contact-card, .link-group, .network-points > div, .flow-grid li, .question-list details"
);

revealItems.forEach((element) => element.classList.add("reveal-item"));

if ("IntersectionObserver" in window) {
  const revealObserver = new IntersectionObserver(
    (entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { rootMargin: "0px 0px -8% 0px", threshold: 0.08 }
  );
  revealItems.forEach((element) => revealObserver.observe(element));
} else {
  revealItems.forEach((element) => element.classList.add("is-visible"));
}

document.querySelectorAll(".project-card").forEach((card) => {
  card.addEventListener("pointermove", (event) => {
    const bounds = card.getBoundingClientRect();
    card.style.setProperty("--spot-x", `${event.clientX - bounds.left}px`);
    card.style.setProperty("--spot-y", `${event.clientY - bounds.top}px`);
  });
  card.addEventListener("pointerleave", () => {
    card.style.removeProperty("--spot-x");
    card.style.removeProperty("--spot-y");
  });
});
