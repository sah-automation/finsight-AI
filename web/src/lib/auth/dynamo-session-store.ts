import 'server-only';

import { DeleteCommand, DynamoDBDocumentClient, GetCommand, PutCommand } from '@aws-sdk/lib-dynamodb';
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';

import type { SessionRecord, SessionStore } from '@/lib/auth/session-store';

interface DynamoSessionStoreOptions {
  tableName: string;
  region: string;
  client?: DynamoDBDocumentClient;
}

function toItem(record: SessionRecord): Record<string, unknown> {
  return {
    session_id: record.id,
    username: record.username,
    access_token: record.accessToken,
    id_token: record.idToken,
    refresh_token: record.refreshToken,
    access_token_expires_at: record.accessTokenExpiresAt,
    created_at: record.createdAt,
    expires_at: Math.floor(record.expiresAt / 1000),
  };
}

function toRecord(item: Record<string, unknown>): SessionRecord | null {
  const id = item.session_id;
  const username = item.username;
  const accessToken = item.access_token;
  const idToken = item.id_token;
  const refreshToken = item.refresh_token;
  const accessTokenExpiresAt = item.access_token_expires_at;
  const createdAt = item.created_at;
  const expiresAt = item.expires_at;
  if (
    typeof id !== 'string' ||
    typeof username !== 'string' ||
    typeof accessToken !== 'string' ||
    typeof idToken !== 'string' ||
    typeof refreshToken !== 'string' ||
    typeof accessTokenExpiresAt !== 'number' ||
    typeof createdAt !== 'number' ||
    typeof expiresAt !== 'number'
  ) {
    return null;
  }
  return {
    id,
    username,
    accessToken,
    idToken,
    refreshToken,
    accessTokenExpiresAt,
    createdAt,
    expiresAt: expiresAt * 1000,
  };
}

/**
 * Server-side session store backed by the shared DynamoDB table. Only the
 * opaque session id travels to the browser.
 */
export class DynamoSessionStore implements SessionStore {
  private readonly tableName: string;
  private readonly client: DynamoDBDocumentClient;

  constructor(options: DynamoSessionStoreOptions) {
    this.tableName = options.tableName;
    this.client =
      options.client ??
      DynamoDBDocumentClient.from(new DynamoDBClient({ region: options.region }), {
        marshallOptions: { removeUndefinedValues: true },
      });
  }

  async get(id: string): Promise<SessionRecord | null> {
    const response = await this.client.send(
      new GetCommand({
        TableName: this.tableName,
        Key: { session_id: id },
        ConsistentRead: true,
      }),
    );
    if (!response.Item) {
      return null;
    }
    return toRecord(response.Item);
  }

  async set(record: SessionRecord): Promise<void> {
    await this.client.send(
      new PutCommand({
        TableName: this.tableName,
        Item: toItem(record),
      }),
    );
  }

  async delete(id: string): Promise<void> {
    await this.client.send(
      new DeleteCommand({
        TableName: this.tableName,
        Key: { session_id: id },
      }),
    );
  }
}
