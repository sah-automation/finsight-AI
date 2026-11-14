import 'server-only';

import type { ServerConfig } from '@/lib/config/server-config';
import { getServerConfig } from '@/lib/config/server-config';
import { CognitoSrpIdentityProvider } from '@/lib/auth/cognito-identity-provider';
import { MockIdentityProvider, getDevMockProvider } from '@/lib/auth/mock-identity-provider';
import { MockCurrentUserClient, getDevMockCurrentUserClient } from '@/lib/auth/mock-current-user';
import {
  BackendCurrentUserClient,
  type CurrentUserClient,
} from '@/lib/auth/current-user';
import { DynamoSessionStore } from '@/lib/auth/dynamo-session-store';
import { SessionService } from '@/lib/auth/session-service';
import { MemorySessionStore, type SessionStore } from '@/lib/auth/session-store';
import type { IdentityProvider } from '@/lib/auth/types';

export interface SessionFactoryDependencies {
  store?: SessionStore;
  identityProvider?: IdentityProvider;
  currentUserClient?: CurrentUserClient;
  clock?: () => number;
}

function sessionStore(config: ServerConfig): SessionStore {
  if (config.sessionStore === 'dynamodb') {
    if (!config.sessionTableName) {
      throw new Error('SESSION_TABLE_NAME is required when SESSION_STORE=dynamodb');
    }
    return new DynamoSessionStore({
      tableName: config.sessionTableName,
      region: config.awsRegion,
    });
  }
  // Use singleton for development to survive across module reloads
  return MemorySessionStore.getInstance();
}

/**
 * Explicit composition so tests can replace one collaborator without touching
 * the environment or the network.
 */
export function createSessionService(
  config: ServerConfig,
  dependencies: SessionFactoryDependencies = {},
): SessionService {
  // Use mock identity provider in development for local testing without Cognito
  const isDev = config.nodeEnv === 'development';
  const identityProvider = isDev
    ? getDevMockProvider()
    : new CognitoSrpIdentityProvider({
        region: config.cognitoRegion,
        userPoolId: config.cognitoUserPoolId,
        clientId: config.cognitoClientId,
      });
  const currentUserClient = isDev
    ? getDevMockCurrentUserClient()
    : new BackendCurrentUserClient({
        backendApiUrl: config.backendApiUrl,
        timeoutMs: config.backendRequestTimeoutMs,
      });

  return new SessionService({
    store: dependencies.store ?? sessionStore(config),
    identityProvider:
      dependencies.identityProvider ?? identityProvider,
    currentUserClient:
      dependencies.currentUserClient ?? currentUserClient,
    ttlSeconds: config.sessionTtlSeconds,
    refreshAheadSeconds: config.sessionRefreshAheadSeconds,
    clock: dependencies.clock,
  });
}

let cached: SessionService | null = null;

export function getSessionService(): SessionService {
  cached ??= createSessionService(getServerConfig());
  return cached;
}

export function resetSessionServiceForTests(): void {
  cached = null;
}
