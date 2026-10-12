import type { PropsWithChildren } from "react";

export function AppShell({ children }: PropsWithChildren) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <h1 className="text-lg font-semibold">AI Business Decision Agent</h1>
        <p className="text-sm text-slate-500">PakManufacture Pvt Ltd &middot; demo / synthetic data</p>
      </header>
      <main className="p-6">{children}</main>
    </div>
  );
}
