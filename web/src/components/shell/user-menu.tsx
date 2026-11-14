import { ChevronDown, LogOut } from 'lucide-react';

import type { CurrentUser } from '@/lib/auth/current-user';
import { messages, roleDisplayName } from '@/lib/messages';

export interface UserMenuProps {
  user: CurrentUser;
}

export function UserMenu({ user }: UserMenuProps) {
  const role = roleDisplayName(user.role_name ?? null, user.role_id);

  return (
    <details className="group relative">
      <summary
        aria-label={messages.userMenu.label}
        className="flex min-h-11 cursor-pointer list-none items-center gap-3 rounded-md px-2 py-2 hover:bg-subtle [&::-webkit-details-marker]:hidden"
      >
        <span
          aria-hidden="true"
          className="flex size-8 shrink-0 items-center justify-center rounded-full bg-inverse text-xs font-medium text-inverse-text"
        >
          {user.company_name.slice(0, 1).toUpperCase()}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-primary">
            {user.company_name}
          </span>
          <span className="block truncate text-xs text-muted">{role}</span>
        </span>
        <ChevronDown
          aria-hidden="true"
          className="size-4 shrink-0 text-muted transition-transform duration-150 group-open:rotate-180"
          strokeWidth={1.5}
        />
      </summary>

      <div className="absolute bottom-full left-0 z-20 mb-2 w-full min-w-56 rounded-lg border border-line bg-surface p-2 shadow-popover">
        <div className="px-2 py-2">
          <p className="text-xs text-muted">{messages.userMenu.signedInAs}</p>
          <p className="truncate text-sm font-medium text-primary">{user.company_name}</p>
          <p className="truncate text-sm text-secondary">{role}</p>
        </div>
        <form action="/api/auth/sign-out" method="post" className="border-t border-line pt-2">
          <button
            type="submit"
            className="flex min-h-11 w-full items-center gap-3 rounded-md px-2 text-sm text-secondary hover:bg-subtle hover:text-primary"
          >
            <LogOut aria-hidden="true" className="size-4 shrink-0" strokeWidth={1.5} />
            {messages.userMenu.signOut}
          </button>
        </form>
      </div>
    </details>
  );
}
