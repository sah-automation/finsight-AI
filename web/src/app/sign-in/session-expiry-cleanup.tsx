'use client';

import { useEffect } from 'react';

/**
 * The server cannot delete cookies while rendering. This one-shot cleanup
 * removes the expired cookie after the graceful redirect to sign in.
 */
export function SessionExpiryCleanup() {
  useEffect(() => {
    void fetch('/api/auth/session', {
      method: 'DELETE',
      credentials: 'same-origin',
      cache: 'no-store',
    });
  }, []);

  return null;
}
