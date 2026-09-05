import React from 'react';
import Link from 'next/link';

export default function NotFound() {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        padding: '2rem',
        textAlign: 'center',
        fontFamily: 'var(--font-family)',
      }}
    >
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: 'var(--radius-xl)',
          background: 'var(--color-surface-secondary)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 'var(--spacing-lg)',
          fontSize: 'var(--font-size-2xl)',
        }}
      >
        404
      </div>
      <h1
        style={{
          fontSize: 'var(--font-size-2xl)',
          fontWeight: 700,
          marginBottom: 'var(--spacing-sm)',
          color: 'var(--color-text-primary)',
        }}
      >
        Page Not Found
      </h1>
      <p
        style={{
          fontSize: 'var(--font-size-sm)',
          color: 'var(--color-text-secondary)',
          marginBottom: 'var(--spacing-xl)',
          maxWidth: 400,
        }}
      >
        The page you&apos;re looking for doesn&apos;t exist or has been moved.
      </p>
      <Link
        href="/"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          padding: '0.75rem 1.5rem',
          background: 'var(--color-brand-dark)',
          color: 'white',
          borderRadius: 'var(--radius-md)',
          fontWeight: 600,
          fontSize: 'var(--font-size-sm)',
          textDecoration: 'none',
          transition: 'background 200ms ease',
        }}
      >
        Return to Dashboard
      </Link>
    </div>
  );
}
