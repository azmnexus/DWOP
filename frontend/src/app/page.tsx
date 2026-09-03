import React from 'react';
import Header from '../components/Header';

export default function HomePage() {
  return (
    <main>
      <Header />
      <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
        <h1>Dynamic Workforce Operations Platform</h1>
        <p>Welcome to DWOP Platform — Multi-tenant workforce management & integration hub.</p>
      </div>
    </main>
  );
}
