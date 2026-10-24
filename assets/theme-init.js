(function () {
  const themes = ["obsidian", "deep-space", "graphite", "aurora", "nebula", "solar-flare"];
  let theme;

  try {
    theme = sessionStorage.getItem("quasar-theme");
  } catch {
    theme = null;
  }

  if (!themes.includes(theme)) {
    theme = themes[Math.floor(Math.random() * themes.length)];
    try {
      sessionStorage.setItem("quasar-theme", theme);
    } catch {
      // The default theme remains usable when browser storage is unavailable.
    }
  }

  document.documentElement.dataset.theme = theme;
  window.quasarTheme = theme;
})();
