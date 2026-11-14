import 'server-only';

import {
  AuthenticationDetails,
  CognitoRefreshToken,
  CognitoUser,
  CognitoUserPool,
  type CognitoUserSession,
  type ICognitoStorage,
} from 'amazon-cognito-identity-js';

import { mapCognitoError } from '@/lib/auth/cognito-errors';
import { SignInError, type IdentityProvider, type TokenSet } from '@/lib/auth/types';

interface CognitoProviderConfig {
  region: string;
  userPoolId: string;
  clientId: string;
}

function memoryStorage(): ICognitoStorage {
  const values = new Map<string, string>();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => {
      values.set(key, value);
    },
    removeItem: (key) => {
      values.delete(key);
    },
    clear: () => {
      values.clear();
    },
  };
}

function tokensFromSession(username: string, session: CognitoUserSession): TokenSet {
  return {
    username,
    accessToken: session.getAccessToken().getJwtToken(),
    idToken: session.getIdToken().getJwtToken(),
    refreshToken: session.getRefreshToken().getToken(),
    accessTokenExpiresAt: session.getAccessToken().getExpiration() * 1000,
  };
}

/**
 * Cognito embedded sign-in using USER_SRP_AUTH.
 *
 * The browser never runs this flow. It posts credentials to the BFF, which
 * keeps the resulting tokens in the server-side session only.
 */
export class CognitoSrpIdentityProvider implements IdentityProvider {
  private readonly config: CognitoProviderConfig;

  constructor(config: CognitoProviderConfig) {
    this.config = config;
  }

  private pool(): CognitoUserPool {
    return new CognitoUserPool({
      UserPoolId: this.config.userPoolId,
      ClientId: this.config.clientId,
      Storage: memoryStorage(),
    });
  }

  async signIn(email: string, password: string): Promise<TokenSet> {
    const pool = this.pool();
    const user = new CognitoUser({ Username: email, Pool: pool });
    const details = new AuthenticationDetails({ Username: email, Password: password });

    return new Promise<TokenSet>((resolve, reject) => {
      user.authenticateUser(details, {
        onSuccess: (session) => {
          resolve(tokensFromSession(email, session));
        },
        onFailure: (error: unknown) => {
          reject(new SignInError(mapCognitoError(error)));
        },
        newPasswordRequired: () => {
          reject(new SignInError('password_reset_required'));
        },
        mfaRequired: () => {
          reject(new SignInError('temporarily_unavailable'));
        },
        totpRequired: () => {
          reject(new SignInError('temporarily_unavailable'));
        },
        customChallenge: () => {
          reject(new SignInError('temporarily_unavailable'));
        },
        mfaSetup: () => {
          reject(new SignInError('temporarily_unavailable'));
        },
        selectMFAType: () => {
          reject(new SignInError('temporarily_unavailable'));
        },
      });
    });
  }

  async refresh(refreshToken: string, username: string): Promise<TokenSet> {
    const pool = this.pool();
    const user = new CognitoUser({ Username: username, Pool: pool });

    return new Promise<TokenSet>((resolve, reject) => {
      user.refreshSession(
        new CognitoRefreshToken({ RefreshToken: refreshToken }),
        (error: unknown, session?: CognitoUserSession) => {
          if (error || !session) {
            reject(new SignInError(mapCognitoError(error)));
            return;
          }
          resolve(tokensFromSession(username, session));
        },
      );
    });
  }
}
