import { useEffect, useState } from "react";

/** Resolve the app's effective theme (accounts for the `system` setting). */
function effective(): "light" | "dark" {
  const dt = document.documentElement.getAttribute("data-theme");
  if (dt === "dark") return "dark";
  if (dt === "light") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Reactively tracks the effective theme (data-theme attr + system preference). */
export function useEffectiveTheme(): "light" | "dark" {
  const [t, setT] = useState<"light" | "dark">(effective);
  useEffect(() => {
    const update = () => setT(effective());
    const mo = new MutationObserver(update);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", update);
    return () => { mo.disconnect(); mq.removeEventListener("change", update); };
  }, []);
  return t;
}
