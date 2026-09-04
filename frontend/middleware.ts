import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Sur app.callbox-ai.com, la racine "/" doit renvoyer directement vers la
 * connexion, pas vers la landing page publique (réservée à callbox-ai.com
 * et www.callbox-ai.com) — les trois domaines pointent vers la même
 * application, seule cette redirection les différencie. AuthContext prend
 * ensuite le relais : un utilisateur déjà identifié est automatiquement
 * renvoyé de /login vers /dashboard.
 */
export function middleware(request: NextRequest) {
  const host = request.headers.get("host") || "";
  const { pathname } = request.nextUrl;

  if (host.startsWith("app.") && pathname === "/") {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: "/",
};
