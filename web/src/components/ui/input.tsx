import type { ComponentProps } from 'react';

import { cn } from '@/lib/cn';

export type InputProps = ComponentProps<'input'>;

export function Input({ className, ...props }: InputProps) {
  return (
    <input
      className={cn(
        'min-h-11 w-full rounded-md border border-line-strong bg-surface px-3 text-sm text-primary',
        'placeholder:text-muted',
        'focus-visible:border-focus focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus',
        'disabled:cursor-not-allowed disabled:bg-subtle disabled:text-muted',
        'aria-invalid:border-negative',
        className,
      )}
      {...props}
    />
  );
}
