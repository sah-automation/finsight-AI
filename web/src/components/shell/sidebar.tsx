import { Menu } from 'lucide-react';
import Link from 'next/link';

import type { CurrentUser } from '@/lib/auth/current-user';
import { messages } from '@/lib/messages';

import { NavLinks } from './nav-links';
import { UserMenu } from './user-menu';

export interface SidebarProps {
  user: CurrentUser;
}

export function Sidebar({ user }: SidebarProps) {
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-line bg-surface shell:flex">
      <div className="px-4 py-5">
        <p className="text-sm font-semibold tracking-tight text-primary">{messages.productName}</p>
        <p className="mt-1 truncate text-xs text-muted">{user.company_name}</p>
      </div>
      <div className="flex-1 px-2 py-2">
        <NavLinks permissions={user.permissions ?? []} />
      </div>
      <div className="border-t border-line p-2">
        <UserMenu user={user} />
      </div>
    </aside>
  );
}

export function MobileHeader({ user }: SidebarProps) {
  return (
    <header className="flex items-center justify-between border-b border-line bg-surface px-4 py-3 shell:hidden">
      <Link href="/" className="text-sm font-semibold tracking-tight text-primary">
        {messages.productName}
      </Link>
      <details className="group relative">
        <summary
          aria-label={messages.navigation.primaryLabel}
          className="flex min-h-11 min-w-11 cursor-pointer list-none items-center justify-center rounded-md text-secondary hover:bg-subtle hover:text-primary [&::-webkit-details-marker]:hidden"
        >
          <Menu aria-hidden="true" className="size-5" strokeWidth={1.5} />
        </summary>
        <div className="absolute right-0 z-30 mt-2 w-72 max-w-[calc(100vw-2rem)] rounded-lg border border-line bg-surface p-2 shadow-popover">
          <div className="px-2 py-2">
            <p className="truncate text-xs text-muted">{user.company_name}</p>
          </div>
          <NavLinks permissions={user.permissions ?? []} />
          <div className="mt-2 border-t border-line pt-2">
            <UserMenu user={user} />
          </div>
        </div>
      </details>
    </header>
  );
}
