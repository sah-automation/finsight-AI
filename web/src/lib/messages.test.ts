import { describe, expect, it } from 'vitest';

import {
  isSignInErrorCode,
  messages,
  roleDisplayName,
  signInMessage,
} from '@/lib/messages';

describe('approved messages', () => {
  it('maps every sign-in error code to an approved message', () => {
    expect(signInMessage('invalid_credentials')).toBe(messages.signIn.invalidCredentials);
    expect(signInMessage('account_locked')).toBe(messages.signIn.accountLocked);
    expect(signInMessage('account_not_confirmed')).toBe(messages.signIn.accountNotConfirmed);
    expect(signInMessage('password_reset_required')).toBe(
      messages.signIn.passwordResetRequired,
    );
    expect(signInMessage('temporarily_unavailable')).toBe(
      messages.signIn.temporarilyUnavailable,
    );
    expect(signInMessage('invalid_request')).toBe(messages.signIn.invalidRequest);
    expect(signInMessage(null)).toBeNull();
  });

  it('rejects unknown error codes so raw API text cannot reach the UI', () => {
    expect(isSignInErrorCode('NotAuthorizedException')).toBe(false);
    expect(isSignInErrorCode('invalid_credentials')).toBe(true);
  });

  it('uses human role names for display only', () => {
    expect(roleDisplayName(null, 'executive_leadership')).toBe('Executive Leadership');
    expect(roleDisplayName('Finance Lead', 'executive_leadership')).toBe('Finance Lead');
    expect(roleDisplayName(null, 'unknown_role')).toBe('Role unavailable');
  });
});
