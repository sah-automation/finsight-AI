import { CircleAlert, Info, TriangleAlert } from 'lucide-react';

import { cn } from '@/lib/cn';

export type NoticeTone = 'info' | 'warning' | 'error';

const toneClasses: Record<NoticeTone, string> = {
  info: 'bg-info-subtle text-info',
  warning: 'bg-warning-subtle text-warning',
  error: 'bg-negative-subtle text-negative',
};

const toneIcon = {
  info: Info,
  warning: TriangleAlert,
  error: CircleAlert,
} as const;

export interface InlineNoticeProps {
  tone?: NoticeTone;
  children: React.ReactNode;
  className?: string;
}

/** Status always carries an icon and text, never colour alone. */
export function InlineNotice({ tone = 'info', children, className }: InlineNoticeProps) {
  const Icon = toneIcon[tone];
  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-md px-3 py-2.5 text-sm leading-5',
        toneClasses[tone],
        className,
      )}
      role={tone === 'error' ? 'alert' : 'status'}
    >
      <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0" strokeWidth={1.5} />
      <div className="min-w-0">{children}</div>
    </div>
  );
}
