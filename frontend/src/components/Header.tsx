import React from 'react';

export default function Header() {
  return (
    <header style={{ padding: '1rem 2rem', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <div style={{ fontWeight: 'bold', fontSize: '1.25rem' }}>DWOP Platform</div>
      <nav style={{ display: 'flex', gap: '1rem' }}>
        <a href="/">Dashboard</a>
        <a href="/people">People</a>
        <a href="/onboarding">Onboarding</a>
        <a href="/assignments">Assignments</a>
        <a href="/access">Access</a>
      </nav>
    </header>
  );
}
