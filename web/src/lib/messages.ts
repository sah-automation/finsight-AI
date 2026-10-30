/**
 * The single approved frontend message set.
 *
 * Every user-facing system message, error, empty state and action label must
 * come from this module. Components never render raw API or Cognito text.
 */

export type SignInErrorCode =
  | 'invalid_credentials'
  | 'account_locked'
  | 'account_not_confirmed'
  | 'password_reset_required'
  | 'temporarily_unavailable'
  | 'invalid_request';

export type SessionReason = 'expired';

export const messages = {
  productName: 'FinSight AI',
  productDescription: 'Ask questions about this company’s documents and verify every number.',
  signIn: {
    title: 'Sign in',
    subtitle: 'Use your company account to continue.',
    emailLabel: 'Email',
    passwordLabel: 'Password', // pragma: allowlist secret
    required: 'Required',
    submit: 'Sign in',
    submitting: 'Signing in',
    invalidCredentials: 'The email or password is incorrect. Please try again.',
    accountLocked: 'This account is locked. Please contact your administrator.',
    accountNotConfirmed:
      'This account is not confirmed yet. Please check your email or contact your administrator.',
    passwordResetRequired: 'You need to reset your password before you can sign in.', // pragma: allowlist secret
    temporarilyUnavailable: 'Login is temporarily unavailable. Please try again.',
    invalidRequest: 'Enter your email and password to sign in.',
  },
  navigation: {
    ask: 'Ask',
    documents: 'Documents',
    upload: 'Upload',
    settings: 'Settings',
    primaryLabel: 'Primary navigation',
    skipToContent: 'Skip to content',
  },
  userMenu: {
    label: 'Account menu',
    signedInAs: 'Signed in as',
    signOut: 'Sign out',
  },
  session: {
    ended: 'Your session ended. Please sign in again.',
  },
  permission: {
    denied: "You don't have access to this.",
  },
  ask: {
    empty: 'Ask a question about this company’s documents.',
  },
  documents: {
    empty: 'No documents yet.',
    loading: 'Loading documents',
    error: 'Documents are temporarily unavailable. Please try again.',
    searchPlaceholder: 'Search documents',
    filterNoResults: 'No documents match your filters.',
    clearFilters: 'Clear filters',
    category: 'Category',
    period: 'Period',
    status: 'Status',
    ingestionState: 'Ingestion state',
    all: 'All',
    upload: 'Upload document',
    delete: 'Delete',
    restore: 'Restore',
    purge: 'Permanently delete',
    recycleBin: 'Recycle bin',
    library: 'Library',
    detailTitle: 'Document details',
    closeDetail: 'Close',
    name: 'Document',
    version: 'Version',
    versions: 'Versions',
    pageCount: 'Pages',
    uploadedBy: 'Uploaded by',
    updated: 'Updated',
    staleContent: 'This document may be affected by a recent change.',
    untitled: 'Untitled document',
    notAvailable: '-',
    deleteConfirm: 'Move this document to the recycle bin?',
    purgeConfirm: 'Permanently delete this document? This cannot be undone.',
    restoreWithin: 'It can be restored within the retention period.',
    deleteSuccess: 'Document moved to the recycle bin.',
    purgeSuccess: 'Document permanently deleted.',
    restoreSuccess: 'Document restored.',
    mutating: 'Updating documents',
  },
  upload: {
    empty: 'Upload a document to get started.',
    title: 'Upload document',
    uploadType: 'Upload type',
    new: 'New',
    update: 'Update',
    category: 'Category',
    period: 'Period',
    periodHint: 'YYYY-QX or YYYY-MM',
    status: 'Status',
    draft: 'Draft',
    final: 'Final',
    replaces: 'Replaces document',
    file: 'File',
    submit: 'Upload document',
    loading: 'Preparing upload',
    uploading: 'Uploading file',
    checkingFile: 'Checking file',
    scanRejected: "Scanned files can't be read in this setup. Please upload a digital file.",
    scanRejectedVirus: 'This file was rejected during security scanning.',
    duplicateTitle: 'This looks like an existing document.',
    updateExisting: 'Update the existing one',
    uploadAsNew: 'Upload as new anyway',
    partitionMissing: "This company isn't set up for uploads yet. Please contact your administrator.",
    success: 'Upload complete.',
    error: 'Upload failed. Please try again.',
    validationRequired: 'Required',
    allowedTypes: 'Allowed types: PDF, XLSX, XLS, CSV, DOCX.',
    progressLabel: 'Upload progress',
  },
  settings: {
    empty: 'Settings for this workspace appear here.',
  },
  working: {
    search: 'Searching documents',
    numbers: 'Checking numbers',
    sources: 'Verifying sources',
  },
  results: {
    wakingUp: 'Waking up, please wait.',
    busy: "We're busy right now. Please try again in a moment.",
    temporarilyUnavailable: 'Temporarily unavailable. Please try again.',
    insufficientData: "I don't have enough data to answer this.",
    needsReview: "Needs review. Some numbers couldn't be read with confidence.",
  },
  actions: {
    tryAgain: 'Try again',
    copy: 'Copy',
    close: 'Close',
  },
} as const;

const signInMessageByCode: Record<SignInErrorCode, string> = {
  invalid_credentials: messages.signIn.invalidCredentials,
  account_locked: messages.signIn.accountLocked,
  account_not_confirmed: messages.signIn.accountNotConfirmed,
  password_reset_required: messages.signIn.passwordResetRequired,
  temporarily_unavailable: messages.signIn.temporarilyUnavailable,
  invalid_request: messages.signIn.invalidRequest,
};

export function signInMessage(code: SignInErrorCode | null | undefined): string | null {
  return code ? signInMessageByCode[code] : null;
}

export function isSignInErrorCode(value: unknown): value is SignInErrorCode {
  return typeof value === 'string' && value in signInMessageByCode;
}

const roleLabels: Record<string, string> = {
  executive_leadership: 'Executive Leadership',
  corporate_finance_planners: 'Corporate Finance & Planners',
  audit_compliance: 'Audit & Compliance',
  system_admin: 'System Admin',
};

/**
 * Display-only role label. Access decisions never use this mapping.
 */
export function roleDisplayName(roleName: string | null, roleId: string): string {
  if (roleName && roleName.trim()) {
    return roleName;
  }
  return roleLabels[roleId] ?? 'Role unavailable';
}
