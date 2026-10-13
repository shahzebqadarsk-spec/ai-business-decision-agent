import { useSelectedClient } from "../context/ClientContext";
import { useClient } from "./useClients";
import { useSystemConfig } from "./useSystemStatus";

/** The currency to format money amounts in, anywhere a KPI result's own `currency` field
 * isn't directly available (dashboard breakdown rows, forecast/scenario pages, RCA issue
 * detail -- none of which carry a currency of their own).
 *
 * Mirrors the same precedence the backend uses (see app/kpi/engine.py's `client_currency`
 * override): the selected client's own auto-detected reporting currency when a client is
 * selected, falling back to the deployment's global default (`/system/config`) for the
 * "All clients (legacy / unscoped)" view or a client with no data materialized yet. */
export function useDisplayCurrency(): string | null {
  const { clientId } = useSelectedClient();
  const clientQuery = useClient(clientId);
  const systemConfigQuery = useSystemConfig();

  if (clientId !== null) {
    return clientQuery.data?.reporting_currency ?? null;
  }
  return systemConfigQuery.data?.currency ?? null;
}
