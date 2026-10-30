'use client';

import {
  FileText,
  MessageSquare,
  Settings,
  Upload,
  type LucideIcon,
} from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { navigationFor, type NavigationId } from '@/lib/auth/permissions';
import { cn } from '@/lib/cn';
import { messages } from '@/lib/messages';

const icons: Record<NavigationId, LucideIcon> = {
  ask: MessageSquare,
  documents: FileText,
  upload: Upload,
  settings: Settings,
};

export interface NavLinksProps {
  permissions: readonly string[];
  onNavigate?: () => void;
}

export function NavLinks({ permissions, onNavigate }: NavLinksProps) {
  const pathname = usePathname();
  const items = navigationFor(permissions);

  if (items.length === 0) {
    return <p className="px-2 text-sm text-muted">{messages.permission.denied}</p>;
  }

  return (
    <nav aria-label={messages.navigation.primaryLabel}>
      <ul className="space-y-1">
        {items.map((item) => {
          const Icon = icons[item.id];
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <li key={item.id}>
              <Link
                href={item.href}
                aria-current={active ? 'page' : undefined}
                onClick={onNavigate}
                className={cn(
                  'flex min-h-11 items-center gap-3 rounded-md px-3 text-sm transition-colors duration-150',
                  active
                    ? 'bg-accent-subtle font-medium text-accent'
                    : 'text-secondary hover:bg-subtle hover:text-primary',
                )}
              >
                <Icon aria-hidden="true" className="size-4 shrink-0" strokeWidth={1.5} />
                <span>{messages.navigation[item.id]}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
