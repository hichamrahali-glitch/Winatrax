/* One-page layout: the left navigation scrolls smoothly to each section and highlights the one in
   view. window.ActiveView ("start", "intro", "map" or "cmp") tells each chart whether its keyboard
   shortcuts apply. Section ids double as URL fragments (#introduction, #world-map, #comparison). */
(() => {
  const links = [...document.querySelectorAll(".sections a")];
  const sections = links.map(a => ({ view: a.dataset.view, el: document.querySelector(a.getAttribute("href")) }));
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");
  function setActive(view) {
    if (window.ActiveView === view) return;
    window.ActiveView = view;
    links.forEach(a => a.setAttribute("aria-current", a.dataset.view === view));
    document.body.classList.toggle("on-hero", view === "start");
    const s = sections.find(x => x.view === view);
    const url = view === "start" ? location.pathname + location.search : "#" + s.el.id;
    if ((view === "start" && location.hash) || (view !== "start" && location.hash !== "#" + s.el.id)) history.replaceState(null, "", url);
  }
  function go(view) {
    const s = sections.find(x => x.view === view);
    s.el.scrollIntoView({ behavior: reduce.matches ? "auto" : "smooth", block: "start" });
    setActive(view);
  }
  // every in-page link to a section (navigation, start button, introduction cards) scrolls smoothly
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    const s = sections.find(x => "#" + x.el.id === a.getAttribute("href"));
    if (s) a.addEventListener("click", ev => { ev.preventDefault(); go(s.view); });
  });
  // the section crossing the middle of the window is the active one
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => { if (e.isIntersecting) setActive(sections.find(s => s.el === e.target).view); });
  }, { rootMargin: "-45% 0px -50% 0px" });
  sections.forEach(s => io.observe(s.el));
  window.CountryComparison && window.CountryComparison.show();
  const fromHash = sections.find(s => location.hash === "#" + s.el.id);
  if (fromHash) { fromHash.el.scrollIntoView({ block: "start" }); setActive(fromHash.view); } else setActive("start");
})();
