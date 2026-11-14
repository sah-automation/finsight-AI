import type { SignInErrorCode } from '@/lib/messages';

export interface TokenSet {
  username: string;
  accessToken: string;
  idToken: string;
  refreshToken: string;
  accessTokenExpiresAt: number;
}

export interface IdentityProvider {
  signIn(email: string, password: string): Promise<TokenSet>;
  refresh(refreshToken: string, username: string): Promise<TokenSet>;
}

export class SignInError extends Error {
  readonly code: SignInErrorCode;

  constructor(code: SignInErrorCode) {
    super(code);
    this.name = 'SignInError';
    this.code = code;
  }
}

export class SessionExpiredError extends Error {
  constructor() {
    super('Session expired');
    this.name = 'SessionExpiredError';
  }
}

export class BackendUnavailableError extends Error {
  constructor(message = 'Backend unavailable') {
    super(message);
    this.name = 'BackendUnavailableError';
  }
}
