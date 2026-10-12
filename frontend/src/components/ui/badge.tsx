import type { PropsWithChildren } from "react";

export function Badge({ children, className = "" }: PropsWithChildren<{ className?: string }>) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>
      {children}
    </span>
  );
}
