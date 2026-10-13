import { useState } from "react";
import { useSelectedClient } from "../context/ClientContext";
import { useClients, useCreateClient } from "../hooks/useClients";

/** Phase 9: lets the person switch which client's/workspace's data they're looking at.
 * "All clients (legacy / unscoped)" preserves the exact pre-Phase-9 behavior -- every
 * upload pooled together -- for data uploaded before clients existed, or for anyone who
 * hasn't started using clients yet. */
export function ClientSwitcher() {
  const { clientId, setClientId } = useSelectedClient();
  const { data: clients, isLoading } = useClients();
  const createClient = useCreateClient();
  const [showNewClientForm, setShowNewClientForm] = useState(false);
  const [newClientName, setNewClientName] = useState("");

  const handleCreate = async () => {
    const name = newClientName.trim();
    if (!name) return;
    const client = await createClient.mutateAsync(name);
    setClientId(client.id);
    setNewClientName("");
    setShowNewClientForm(false);
  };

  const selected = clients?.find((c) => c.id === clientId);

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="client-switcher" className="text-sm text-slate-500">
        Client:
      </label>
      <select
        id="client-switcher"
        className="rounded border border-slate-300 bg-white px-2 py-1 text-sm"
        value={clientId ?? ""}
        disabled={isLoading}
        onChange={(e) => {
          const value = e.target.value;
          if (value === "__new__") {
            setShowNewClientForm(true);
            return;
          }
          setClientId(value === "" ? null : value);
        }}
      >
        <option value="">All clients (legacy / unscoped)</option>
        {clients?.map((client) => (
          <option key={client.id} value={client.id}>
            {client.name}
            {client.reporting_currency ? ` (${client.reporting_currency})` : ""}
          </option>
        ))}
        <option value="__new__">+ New client&hellip;</option>
      </select>
      {selected && !selected.reporting_currency && (
        <span className="text-xs text-amber-600">No data uploaded yet -- currency not detected.</span>
      )}

      {showNewClientForm && (
        <div className="flex items-center gap-1">
          <input
            autoFocus
            type="text"
            placeholder="Client name"
            className="rounded border border-slate-300 px-2 py-1 text-sm"
            value={newClientName}
            onChange={(e) => setNewClientName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void handleCreate();
              if (e.key === "Escape") {
                setShowNewClientForm(false);
                setNewClientName("");
              }
            }}
          />
          <button
            type="button"
            className="rounded bg-slate-800 px-2 py-1 text-xs font-medium text-white disabled:opacity-50"
            disabled={createClient.isPending || newClientName.trim() === ""}
            onClick={() => void handleCreate()}
          >
            Create
          </button>
          <button
            type="button"
            className="rounded px-2 py-1 text-xs text-slate-500"
            onClick={() => {
              setShowNewClientForm(false);
              setNewClientName("");
            }}
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
