'use client';

import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle, AlertTriangle, Info, X, XCircle } from 'lucide-react';
import styles from './ui.module.css';

type ToastType = 'success' | 'error' | 'warning' | 'info';

interface ToastMessage {
  id: string;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  showToast: (type: ToastType, message: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

const toastIcons: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle size={18} color="var(--color-success)" />,
  error: <XCircle size={18} color="var(--color-error)" />,
  warning: <AlertTriangle size={18} color="var(--color-warning)" />,
  info: <Info size={18} color="var(--color-info)" />,
};

const toastStyles: Record<ToastType, string> = {
  success: styles.toastSuccess,
  error: styles.toastError,
  warning: styles.toastWarning,
  info: styles.toastInfo,
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const showToast = useCallback((type: ToastType, message: string) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setToasts(prev => [...prev, { id, type, message }]);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 5000);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className={styles.toastContainer} aria-live="polite" aria-label="Notifications">
        {toasts.map(toast => (
          <div key={toast.id} className={`${styles.toast} ${toastStyles[toast.type]}`} role="status">
            <span className={styles.toastIcon}>{toastIcons[toast.type]}</span>
            <span className={styles.toastMessage}>{toast.message}</span>
            <button
              className={styles.toastClose}
              onClick={() => dismiss(toast.id)}
              aria-label="Dismiss notification"
            >
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}
