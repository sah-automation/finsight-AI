import 'server-only';

export type SessionStoreKind = 'memory' | 'dynamodb';

export interface ServerConfig {
  nodeEnv: string;
  backendApiUrl: string;
  backendRequestTimeoutMs: number;
  cognitoRegion: string;
  cognitoUserPoolId: string;
  cognitoClientId: string;
  sessionStore: SessionStoreKind;
  sessionTableName: string | null;
  sessionCookieName: string;
  sessionCookieSecure: boolean;
  sessionTtlSeconds: number;
  sessionRefreshAheadSeconds: number;
  awsRegion: string;
}

export class ServerConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ServerConfigError';
  }
}

function required(env: NodeJS.ProcessEnv, name: string): string {
  const value = env[name]?.trim();
  if (!value) {
    throw new ServerConfigError(`Missing required server configuration: ${name}`);
  }
  return value;
}

function integer(
  env: NodeJS.ProcessEnv,
  name: string,
  fallback: number,
  min: number,
  max: number,
): number {
  const raw = env[name]?.trim();
  if (!raw) {
    return fallback;
  }
  if (!/^\d+$/.test(raw)) {
    throw new ServerConfigError(`${name} must be a whole number`);
  }
  const value = Number(raw);
  if (value < min || value > max) {
    throw new ServerConfigError(`${name} must be between ${min} and ${max}`);
  }
  return value;
}

function boolean(env: NodeJS.ProcessEnv, name: string, fallback: boolean): boolean {
  const raw = env[name]?.trim().toLowerCase();
  if (!raw) {
    return fallback;
  }
  if (raw === 'true') {
    return true;
  }
  if (raw === 'false') {
    return false;
  }
  throw new ServerConfigError(`${name} must be true or false`);
}

function parseBackendUrl(raw: string): string {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new ServerConfigError('BACKEND_API_URL must be a valid absolute URL');
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new ServerConfigError('BACKEND_API_URL must use http or https');
  }
  url.search = '';
  url.hash = '';
  return url.toString().replace(/\/$/, '');
}

export function parseServerConfig(env: NodeJS.ProcessEnv): ServerConfig {
  const nodeEnv = env.NODE_ENV?.trim() || 'development';
  const sessionStoreRaw = (env.SESSION_STORE?.trim() || 'memory').toLowerCase();
  if (sessionStoreRaw !== 'memory' && sessionStoreRaw !== 'dynamodb') {
    throw new ServerConfigError('SESSION_STORE must be memory or dynamodb');
  }

  const sessionCookieSecure = boolean(env, 'SESSION_COOKIE_SECURE', true);
  if (nodeEnv === 'production' && !sessionCookieSecure) {
    throw new ServerConfigError('SESSION_COOKIE_SECURE must stay on in production');
  }

  const sessionTableName = env.SESSION_TABLE_NAME?.trim() || null;
  if (sessionStoreRaw === 'dynamodb' && !sessionTableName) {
    throw new ServerConfigError('SESSION_TABLE_NAME is required when SESSION_STORE=dynamodb');
  }

  const cognitoRegion = required(env, 'COGNITO_REGION');
  const refreshTokenDays = integer(env, 'AUTH_REFRESH_TOKEN_DAYS', 7, 1, 30);

  return {
    nodeEnv,
    backendApiUrl: parseBackendUrl(required(env, 'BACKEND_API_URL')),
    backendRequestTimeoutMs: integer(env, 'BACKEND_REQUEST_TIMEOUT_MS', 10_000, 500, 120_000),
    cognitoRegion,
    cognitoUserPoolId: required(env, 'COGNITO_USER_POOL_ID'),
    cognitoClientId: required(env, 'COGNITO_CLIENT_ID'),
    sessionStore: sessionStoreRaw,
    sessionTableName,
    sessionCookieName: env.SESSION_COOKIE_NAME?.trim() || 'finsight_session',
    sessionCookieSecure,
    sessionTtlSeconds: refreshTokenDays * 24 * 60 * 60,
    sessionRefreshAheadSeconds: integer(env, 'SESSION_REFRESH_AHEAD_SECONDS', 60, 0, 600),
    awsRegion: env.AWS_REGION?.trim() || cognitoRegion,
  };
}

let cached: ServerConfig | null = null;

export function getServerConfig(): ServerConfig {
  cached ??= parseServerConfig(process.env);
  return cached;
}

export function resetServerConfigForTests(): void {
  cached = null;
}
