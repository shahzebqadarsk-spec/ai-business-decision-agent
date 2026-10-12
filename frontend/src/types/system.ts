export interface SystemConfig {
  currency: string;
  fiscal_year_start_month: number;
  default_comparison: string;
  synthetic_data_only: boolean;
  llm_use_mock: boolean;
}

export interface LlmStatus {
  use_mock: boolean;
  deepseek_key_present: boolean;
  routes: Record<string, string>;
}
