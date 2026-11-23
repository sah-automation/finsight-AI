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

  it('holds the new §5.2 approved strings verbatim', () => {
    expect(messages.results.stillWorking).toBe('Still working on your question.');
    expect(messages.dashboard.figuresPreparing).toBe('Figures are being prepared.');
    expect(messages.dashboard.layoutChanged).toBe(
      'The layout changed elsewhere. Check the current layout and save again to reapply.',
    );
  });

  it('holds the §5.2 strings that are approved verbatim', () => {
    expect(messages.results.stopped).toBe('Stopped. Ask again or rephrase.');
    expect(messages.dashboard.noFigures).toBe('No figures yet');
    expect(messages.dashboard.askFinanceTeam).toBe(
      'Ask your finance team to upload documents.',
    );
    expect(messages.permission.denied).toBe("You don't have access to this.");
  });

  it('uses human role names for display only', () => {
    expect(roleDisplayName(null, 'executive_leadership')).toBe('Executive Leadership');
    expect(roleDisplayName('Finance Lead', 'executive_leadership')).toBe('Finance Lead');
    expect(roleDisplayName(null, 'unknown_role')).toBe('Role unavailable');
  });
});
