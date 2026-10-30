import type { ComponentProps } from 'react';

import { cn } from '@/lib/cn';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive';

export interface ButtonProps extends ComponentProps<'button'> {
  variant?: ButtonVariant;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: 'bg-inverse text-inverse-text hover:opacity-90',
  secondary: 'border border-line-strong bg-surface text-primary hover:bg-subtle',
  ghost: 'text-secondary hover:bg-subtle hover:text-primary',
  destructive: 'bg-negative text-inverse-text hover:opacity-90',
};

export function Button({
  type = 'button',
  variant = 'primary',
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-4 text-sm font-medium transition-colors duration-150',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus',
        'disabled:cursor-not-allowed disabled:opacity-60',
        variantClasses[variant],
        className,
      )}
      {...props}
    />
  );
}
