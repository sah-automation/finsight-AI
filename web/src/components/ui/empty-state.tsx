import { cn } from '@/lib/cn';

export interface EmptyStateProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'rounded-lg border border-line bg-surface px-6 py-10 text-center',
        className,
      )}
    >
      <p className="text-sm font-medium text-primary">{title}</p>
      {description ? <p className="mt-2 text-sm text-secondary">{description}</p> : null}
      {action ? <div className="mt-6 flex justify-center">{action}</div> : null}
    </div>
  );
}
