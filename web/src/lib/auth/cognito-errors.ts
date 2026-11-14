import type { SignInErrorCode } from '@/lib/messages';

interface CognitoErrorLike {
  code?: unknown;
  name?: unknown;
  message?: unknown;
}

const temporaryCodes = new Set([
  'TooManyRequestsException',
  'TooManyFailedAttemptsException',
  'LimitExceededException',
  'InternalErrorException',
  'ServiceUnavailable',
  'ServiceUnavailableException',
  'NetworkingError',
  'TimeoutError',
]);

function errorCode(error: unknown): string {
  if (!error || typeof error !== 'object') {
    return '';
  }
  const candidate = error as CognitoErrorLike;
  return String(candidate.code ?? candidate.name ?? '');
}

function errorMessage(error: unknown): string {
  if (!error || typeof error !== 'object') {
    return '';
  }
  return String((error as CognitoErrorLike).message ?? '');
}

/**
 * Map identity-provider failures onto the approved message codes. Unknown
 * errors never leak through to the browser.
 */
export function mapCognitoError(error: unknown): SignInErrorCode {
  const code = errorCode(error);
  const message = errorMessage(error).toLowerCase();

  if (temporaryCodes.has(code)) {
    return 'temporarily_unavailable';
  }
  if (code === 'UserNotConfirmedException') {
    return 'account_not_confirmed';
  }
  if (code === 'PasswordResetRequiredException') {
    return 'password_reset_required';
  }
  if (code === 'NotAuthorizedException' || code === 'UserNotFoundException') {
    if (message.includes('attempts') || message.includes('locked')) {
      return 'account_locked';
    }
    return 'invalid_credentials';
  }
  if (code === 'InvalidParameterException' || code === 'InvalidPasswordException') {
    return 'invalid_request';
  }
  return 'temporarily_unavailable';
}
