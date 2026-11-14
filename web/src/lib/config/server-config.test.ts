import { describe, expect, it } from 'vitest';

import { parseServerConfig, ServerConfigError } from '@/lib/config/server-config';

function env(overrides: Record<string, string> = {}): NodeJS.ProcessEnv {
  return {
    BACKEND_API_URL: 'https://api.example.com/',
    COGNITO_REGION: 'us-east-1',
    COGNITO_USER_POOL_ID: 'us-east-1_test',
    COGNITO_CLIENT_ID: 'client-id',
    ...overrides,
  } as unknown as NodeJS.ProcessEnv;
}

describe('server config', () => {
  it('parses the required settings and safe defaults', () => {
    const config = parseServerConfig(env());
    expect(config.backendApiUrl).toBe('https://api.example.com');
    expect(config.sessionStore).toBe('memory');
    expect(config.sessionCookieName).toBe('finsight_session');
    expect(config.sessionCookieSecure).toBe(true);
    expect(config.sessionTtlSeconds).toBe(7 * 24 * 60 * 60);
    expect(config.awsRegion).toBe('us-east-1');
  });

  it('never allows an insecure session cookie in production', () => {
    expect(() =>
      parseServerConfig(env({ NODE_ENV: 'production', SESSION_COOKIE_SECURE: 'false' })),
    ).toThrow(ServerConfigError);
  });

  it('requires a session table for the DynamoDB store', () => {
    expect(() => parseServerConfig(env({ SESSION_STORE: 'dynamodb' }))).toThrow(
      /SESSION_TABLE_NAME/,
    );
    expect(
      parseServerConfig(
        env({ SESSION_STORE: 'dynamodb', SESSION_TABLE_NAME: 'finsight-sessions' }),
      ).sessionTableName,
    ).toBe('finsight-sessions');
  });

  it('fails loudly on malformed values', () => {
    expect(() => parseServerConfig(env({ BACKEND_API_URL: 'not-a-url' }))).toThrow(
      /BACKEND_API_URL/,
    );
    expect(() => parseServerConfig(env({ BACKEND_REQUEST_TIMEOUT_MS: 'soon' }))).toThrow(
      /whole number/,
    );
    expect(() => parseServerConfig(env({ SESSION_COOKIE_SECURE: 'maybe' }))).toThrow(
      /true or false/,
    );
    expect(() => parseServerConfig(env({ SESSION_STORE: 'redis' }))).toThrow(
      /memory or dynamodb/,
    );
    expect(() => parseServerConfig(env({ COGNITO_CLIENT_ID: '' }))).toThrow(
      /COGNITO_CLIENT_ID/,
    );
  });
});
