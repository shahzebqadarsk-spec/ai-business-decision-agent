import { Card } from "../components/ui/card";
import { useLlmStatus, useSystemConfig } from "../hooks/useSystemStatus";

export function StatusPage() {
  const configQuery = useSystemConfig();
  const llmQuery = useLlmStatus();

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Card>
        <h2 className="mb-2 text-sm font-semibold text-slate-500">System configuration</h2>
        {configQuery.isLoading && <p>Loading...</p>}
        {configQuery.isError && <p className="text-red-600">Could not reach the backend.</p>}
        {configQuery.data && (
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between">
              <dt>Currency</dt>
              <dd>{configQuery.data.currency}</dd>
            </div>
            <div className="flex justify-between">
              <dt>Default comparison</dt>
              <dd>{configQuery.data.default_comparison}</dd>
            </div>
            <div className="flex justify-between">
              <dt>Synthetic data only</dt>
              <dd>{String(configQuery.data.synthetic_data_only)}</dd>
            </div>
          </dl>
        )}
      </Card>
      <Card>
        <h2 className="mb-2 text-sm font-semibold text-slate-500">LLM routing</h2>
        {llmQuery.isLoading && <p>Loading...</p>}
        {llmQuery.isError && <p className="text-red-600">Could not reach the backend.</p>}
        {llmQuery.data && (
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between">
              <dt>Mock provider</dt>
              <dd>{String(llmQuery.data.use_mock)}</dd>
            </div>
            <div className="flex justify-between">
              <dt>DeepSeek key present</dt>
              <dd>{String(llmQuery.data.deepseek_key_present)}</dd>
            </div>
          </dl>
        )}
      </Card>
    </div>
  );
}
