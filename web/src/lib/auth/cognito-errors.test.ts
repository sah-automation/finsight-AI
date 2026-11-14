import { describe, expect, it } from 'vitest';

import { mapCognitoError } from '@/lib/auth/cognito-errors';

describe('mapCognitoError', () => {
  it('maps the approved sign-in failure families', () => {
    expect(mapCognitoError({ code: 'NotAuthorizedException' })).toBe('invalid_credentials');
    expect(mapCognitoError({ code: 'NotAuthorizedException', message: 'Too many attempts' })).toBe(
      'account_locked',
    );
    expect(mapCognitoError({ code: 'UserNotFoundException' })).toBe('invalid_credentials');
    expect(mapCognitoError({ code: 'UserNotConfirmedException' })).toBe(
      'account_not_confirmed',
    );
    expect(mapCognitoError({ code: 'PasswordResetRequiredException' })).toBe(
      'password_reset_required',
    );
    expect(mapCognitoError({ code: 'InvalidParameterException' })).toBe('invalid_request');
  });

  it('treats throttling and unknown failures as temporary', () => {
    expect(mapCognitoError({ code: 'TooManyRequestsException' })).toBe(
      'temporarily_unavailable',
    );
    expect(mapCognitoError({ code: 'NetworkingError' })).toBe('temporarily_unavailable');
    expect(mapCognitoError(new Error('raw provider text'))).toBe('temporarily_unavailable');
    expect(mapCognitoError(null)).toBe('temporarily_unavailable');
  });
});
