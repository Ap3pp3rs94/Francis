export type FrancisSurface = "frontend" | "backend";

export function normalizeFrancisSurfacePath(pathname: string): string {
  const normalized = String(pathname || "/").trim().replace(/\/+$/, "");
  return normalized || "/";
}

export function francisSurfaceForPath(pathname: string): FrancisSurface {
  const path = normalizeFrancisSurfacePath(pathname);
  return path === "/backend" || path === "/diagnostics" ? "backend" : "frontend";
}

export function francisSurfaceHref(surface: FrancisSurface): string {
  return surface === "backend" ? "/backend" : "/frontend";
}
