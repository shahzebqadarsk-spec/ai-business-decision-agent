import { apiGet, apiPostJson } from "./client";
import type { Client } from "../types/client";

export function listClients(): Promise<Client[]> {
  return apiGet<Client[]>("/clients");
}

export function getClient(clientId: string): Promise<Client> {
  return apiGet<Client>(`/clients/${clientId}`);
}

export function createClient(name: string): Promise<Client> {
  return apiPostJson<Client>("/clients", { name });
}
