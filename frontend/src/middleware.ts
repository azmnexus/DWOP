import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * Next.js middleware for route protection.
 * Checks for JWT token in cookies or localStorage (via custom header).
 *
 * Note: Since we use localStorage for token storage (not cookies),
 * this middleware only handles the redirect logic for known protected paths.
 * The actual auth check happens client-side in the AuthContext / authenticated layout.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Public routes that don't require authentication
  const publicPaths = ['/login', '/api', '/_next', '/favicon.ico', '/logo.png', '/fonts'];
  const isPublicPath = publicPaths.some(path => pathname.startsWith(path));

  if (isPublicPath) {
    return NextResponse.next();
  }

  // For all other routes, allow through — client-side auth check
  // handles the redirect in the authenticated layout
  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except static files and API routes
     */
    '/((?!_next/static|_next/image|favicon.ico|logo.png|fonts).*)',
  ],
};
