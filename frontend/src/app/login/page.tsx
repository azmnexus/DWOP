'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Mail, Lock, AlertCircle } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import styles from './login.module.css';

export default function LoginPage() {
  const router = useRouter();
  const { login, isLoggedIn, isLoading: authLoading, error: authError } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Redirect if already logged in
  useEffect(() => {
    if (isLoggedIn && !authLoading) {
      router.replace('/');
    }
  }, [isLoggedIn, authLoading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!email.trim()) {
      setFormError('Please enter your email address.');
      return;
    }
    if (!password) {
      setFormError('Please enter your password.');
      return;
    }

    setIsSubmitting(true);
    try {
      await login({ email: email.trim(), password });
      router.replace('/');
    } catch {
      // Error is already set in AuthContext
      setFormError(authError || 'Invalid credentials. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Don't render login form if already authenticated
  if (isLoggedIn && !authLoading) {
    return null;
  }

  return (
    <div className={styles.loginPage}>
      <div className={styles.loginCard}>
        {/* Icon Badge — AZM Nexus logomark in rounded-square badge */}
        <div className={styles.logoBadge}>
          <img src="/logo.png" alt="AZM Nexus" width={36} height={36} />
        </div>

        {/* Heading */}
        <h1 className={styles.loginHeading}>Initialize Session</h1>

        {/* Subtext */}
        <p className={styles.loginSubtext}>
          AZM Nexus workforce operations platform.<br />
          Secure your digital identity.
        </p>

        {/* Error Alert */}
        {(formError || authError) && (
          <div className={styles.loginError} role="alert">
            <AlertCircle size={16} />
            <span>{formError || authError}</span>
          </div>
        )}

        {/* Login Form */}
        <form className={styles.loginForm} onSubmit={handleSubmit} noValidate>
          <Input
            label="User Identifier"
            type="email"
            placeholder="email@azm-nexus.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            icon={<Mail size={18} />}
            autoComplete="email"
            autoFocus
            required
            aria-label="Email address"
          />

          <Input
            label="Passkey"
            type="password"
            placeholder="Enter your passkey"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            icon={<Lock size={18} />}
            autoComplete="current-password"
            required
            aria-label="Password"
          />

          {/* Keep session + Recover Access — side by side */}
          <div className={styles.sessionRecoverRow}>
            <div className={styles.sessionRow}>
              <input
                type="checkbox"
                id="keep-session"
                className={styles.sessionCheckbox}
                defaultChecked
              />
              <label htmlFor="keep-session" className={styles.sessionLabel}>
                Keep session active
              </label>
            </div>
            <span className={styles.recoverLink}>Recover Access</span>
          </div>

          {/* Submit Button — full-width, pill, dark fill per Reference A */}
          <div className={styles.submitArea}>
            <Button
              type="submit"
              variant="primary"
              size="md"
              fullWidth
              loading={isSubmitting}
            >
              Initialize Session →
            </Button>
          </div>
        </form>

        {/* Footer */}
        <div className={styles.loginFooter}>
          <div className={styles.footerLabel}>AZM Nexus Secure Portal</div>
          <div className={styles.footerDemo}>
            Demo: <span className={styles.footerDemoCredential}>admin@azm-nexus.com</span> / <span className={styles.footerDemoCredential}>Admin123!</span>
          </div>
        </div>
      </div>
    </div>
  );
}
