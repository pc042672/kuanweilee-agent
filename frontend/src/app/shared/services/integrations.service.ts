import { Injectable, computed, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

export interface ServiceStatus {
  service: string;
  label: string;
  configured: boolean;
  source: 'db' | 'env' | null;
  metadata: Record<string, string>;
  hint: string | null;
  updated_at: string | null;
  secret_fields: string[];
  metadata_fields: string[];
}

export interface DataSource {
  id: number;
  name: string;
  db_type: string;
  connection_config: Record<string, any>;
  is_active: boolean;
  has_secrets: boolean;
}

export interface DataSourcePayload {
  name: string;
  db_type: string;
  connection_config: Record<string, any>;
  /** Omit (undefined) to keep stored secrets unchanged on update. */
  secrets?: Record<string, string>;
  is_active: boolean;
}

export interface TestResult {
  ok: boolean;
  error?: string;
  latency_ms?: number;
  server_version?: string;
}

@Injectable({ providedIn: 'root' })
export class IntegrationsService {
  private readonly API_BASE = '/api/integrations';

  private http = inject(HttpClient);

  private static errMsg(e: any, fallback: string): string {
    return String(e?.error?.detail || e?.message || fallback);
  }

  private servicesSignal = signal<ServiceStatus[]>([]);
  private dataSourcesSignal = signal<DataSource[]>([]);
  /** Agent tool name -> services it requires (tool is disabled until configured). */
  private gatedToolsSignal = signal<Record<string, string[]>>({});
  /** Inverted once: service -> agent tools it gates. */
  private toolsByService = computed(() => {
    const inverted: Record<string, string[]> = {};
    for (const [tool, services] of Object.entries(this.gatedToolsSignal())) {
      for (const s of services) (inverted[s] ??= []).push(tool);
    }
    return inverted;
  });
  private loading = signal(false);

  readonly services = this.servicesSignal.asReadonly();
  readonly dataSources = this.dataSourcesSignal.asReadonly();
  readonly isLoading = this.loading.asReadonly();

  async loadAll(): Promise<void> {
    this.loading.set(true);
    try {
      await Promise.all([this.loadServices(), this.loadDataSources()]);
    } finally {
      this.loading.set(false);
    }
  }

  // ==================== External services ====================

  async loadServices(): Promise<void> {
    try {
      const r = await firstValueFrom(
        this.http.get<{ services: ServiceStatus[]; gated_tools?: Record<string, string[]> }>(
          `${this.API_BASE}/services`
        )
      );
      this.servicesSignal.set(r.services);
      this.gatedToolsSignal.set(r.gated_tools ?? {});
    } catch (e) {
      console.warn('Failed to load integration services:', e);
    }
  }

  /** Agent tools gated behind the given service. */
  toolsGatedBy(service: string): string[] {
    return this.toolsByService()[service] ?? [];
  }

  async saveService(
    service: string, secrets: Record<string, string>, metadata: Record<string, string>
  ): Promise<{ success: boolean; error?: string }> {
    try {
      await firstValueFrom(
        this.http.put(`${this.API_BASE}/services/${service}`, { secrets, metadata })
      );
      await this.loadServices();
      return { success: true };
    } catch (e: any) {
      return { success: false, error: IntegrationsService.errMsg(e, 'Save failed') };
    }
  }

  async deleteService(service: string): Promise<boolean> {
    try {
      await firstValueFrom(this.http.delete(`${this.API_BASE}/services/${service}`));
      await this.loadServices();
      return true;
    } catch (e) {
      console.error('Failed to remove service credentials:', e);
      return false;
    }
  }

  async testService(service: string): Promise<TestResult> {
    try {
      return await firstValueFrom(
        this.http.post<TestResult>(`${this.API_BASE}/services/${service}/test`, {})
      );
    } catch (e: any) {
      return { ok: false, error: IntegrationsService.errMsg(e, 'Test failed') };
    }
  }

  // ==================== Data sources ====================

  async loadDataSources(): Promise<void> {
    try {
      const r = await firstValueFrom(
        this.http.get<{ data_sources: DataSource[] }>(`${this.API_BASE}/data-sources`)
      );
      this.dataSourcesSignal.set(r.data_sources);
    } catch (e) {
      console.warn('Failed to load data sources:', e);
    }
  }

  async saveDataSource(
    payload: DataSourcePayload, id?: number
  ): Promise<{ success: boolean; error?: string }> {
    try {
      if (id != null) {
        await firstValueFrom(this.http.put(`${this.API_BASE}/data-sources/${id}`, payload));
      } else {
        await firstValueFrom(this.http.post(`${this.API_BASE}/data-sources`, payload));
      }
      await this.loadDataSources();
      return { success: true };
    } catch (e: any) {
      return { success: false, error: IntegrationsService.errMsg(e, 'Save failed') };
    }
  }

  async deleteDataSource(id: number): Promise<boolean> {
    try {
      await firstValueFrom(this.http.delete(`${this.API_BASE}/data-sources/${id}`));
      await this.loadDataSources();
      return true;
    } catch (e) {
      console.error('Failed to delete data source:', e);
      return false;
    }
  }

  /** Pre-save test from form values (secrets must be included in the payload). */
  async testDataSourceConfig(payload: DataSourcePayload): Promise<TestResult> {
    try {
      return await firstValueFrom(
        this.http.post<TestResult>(`${this.API_BASE}/data-sources/test`, payload)
      );
    } catch (e: any) {
      return { ok: false, error: IntegrationsService.errMsg(e, 'Test failed') };
    }
  }

  /** Test a stored data source using its encrypted secrets. */
  async testDataSource(id: number): Promise<TestResult> {
    try {
      return await firstValueFrom(
        this.http.post<TestResult>(`${this.API_BASE}/data-sources/${id}/test`, {})
      );
    } catch (e: any) {
      return { ok: false, error: IntegrationsService.errMsg(e, 'Test failed') };
    }
  }
}
