import type { PropsWithChildren } from "react";
import { ClientSwitcher } from "./ClientSwitcher";

export function AppShell({ children }: PropsWithChildren) {
  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
        <div>
          <h1 className="text-lg font-semibold">AI Business Decision Agent</h1>
          <p className="text-sm text-slate-500">Select a client below to view its own data and currency.</p>
        </div>
        <ClientSwitcher />
      </header>
      <main className="p-6">{children}</main>
    </div>
  );
}
