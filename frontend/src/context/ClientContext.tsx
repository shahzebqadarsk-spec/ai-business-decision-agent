import { createContext, useContext, useState, type PropsWithChildren } from "react";

const STORAGE_KEY = "abda.selectedClientId";

interface ClientContextValue {
  /** `null` means "all clients" / unscoped -- the pre-Phase-9 behavior of pooling every
   * upload together. Selecting a client scopes every dashboard/KPI/RCA/forecast/scenario
   * call to that one client's own data and its own resolved reporting currency. */
  clientId: string | null;
  setClientId: (clientId: string | null) => void;
}

const ClientContext = createContext<ClientContextValue | undefined>(undefined);

function readStoredClientId(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function ClientProvider({ children }: PropsWithChildren) {
  const [clientId, setClientIdState] = useState<string | null>(() => readStoredClientId());

  const setClientId = (next: string | null) => {
    setClientIdState(next);
    try {
      if (next === null) {
        window.localStorage.removeItem(STORAGE_KEY);
      } else {
        window.localStorage.setItem(STORAGE_KEY, next);
      }
    } catch {
      // Best-effort only -- the in-memory selection above still works for this session.
    }
  };

  return <ClientContext.Provider value={{ clientId, setClientId }}>{children}</ClientContext.Provider>;
}

export function useSelectedClient(): ClientContextValue {
  const ctx = useContext(ClientContext);
  if (ctx === undefined) {
    throw new Error("useSelectedClient must be used within a ClientProvider");
  }
  return ctx;
}
