import React from 'react';
import styles from './ui.module.css';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helper?: string;
  icon?: React.ReactNode;
}

export function Input({
  label,
  error,
  helper,
  icon,
  id,
  className = '',
  ...props
}: InputProps) {
  const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');

  return (
    <div className={`${styles.inputWrapper} ${error ? styles.inputError : ''} ${className}`}>
      {label && (
        <label htmlFor={inputId} className={styles.inputLabel}>
          {label}
        </label>
      )}
      <div className={styles.inputContainer}>
        {icon && <span className={styles.inputIcon}>{icon}</span>}
        <input
          id={inputId}
          className={`${styles.inputField} ${icon ? styles.inputWithIcon : ''}`}
          aria-invalid={!!error}
          aria-describedby={error ? `${inputId}-error` : helper ? `${inputId}-helper` : undefined}
          {...props}
        />
      </div>
      {error && (
        <span id={`${inputId}-error`} className={styles.inputErrorText} role="alert">
          {error}
        </span>
      )}
      {helper && !error && (
        <span id={`${inputId}-helper`} className={styles.inputHelper}>
          {helper}
        </span>
      )}
    </div>
  );
}
