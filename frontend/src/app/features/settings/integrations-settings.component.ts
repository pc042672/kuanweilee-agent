import { Component, signal, inject, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { DialogModule } from 'primeng/dialog';
import { TooltipModule } from 'primeng/tooltip';
import { TagModule } from 'primeng/tag';
import {
  IntegrationsService, ServiceStatus, DataSource, DataSourcePayload, TestResult
} from '../../shared/services/integrations.service';
import { AuthService } from '../../shared/services/auth.service';

type Tab = 'datasources' | 'services';

const DB_TYPES = ['greenplum', 'postgresql', 'mysql', 'mssql', 'oracle'];

@Component({
  selector: 'app-integrations-settings',
  standalone: true,
  imports: [CommonModule, FormsModule, ButtonModule, InputTextModule, DialogModule, TooltipModule, TagModule],
  template: `
    <div class="integrations-settings">
      <div class="page-header">
        <div>
          <h1>Integrations</h1>
          <p>Per-site data sources and external service credentials</p>
        </div>
        <div class="header-actions">
          <button pButton label="Reload" icon="pi pi-refresh" class="p-button-outlined"
                  (click)="reload()" [loading]="loading()"></button>
          @if (activeTab() === 'datasources' && isAdmin()) {
            <button pButton label="Add Data Source" icon="pi pi-plus" (click)="openAddDataSource()"></button>
          }
        </div>
      </div>

      <div class="type-tabs">
        <button class="type-tab" [class.active]="activeTab() === 'datasources'"
                (click)="activeTab.set('datasources')">
          Data Sources <span class="tab-count">{{ dataSources().length }}</span>
        </button>
        <button class="type-tab" [class.active]="activeTab() === 'services'"
                (click)="activeTab.set('services')">
          External Services <span class="tab-count">{{ configuredServiceCount() }}/{{ services().length }}</span>
        </button>
      </div>

      <!-- ===================== DATA SOURCES ===================== -->
      @if (activeTab() === 'datasources') {
        <div class="cards-grid">
          @for (ds of dataSources(); track ds.id) {
            <div class="item-card glass-card" [class.inactive]="!ds.is_active">
              <div class="card-header">
                <div class="card-title">
                  <span class="type-badge">{{ ds.db_type }}</span>
                  <span class="card-name">{{ ds.name }}</span>
                  @if (!ds.is_active) { <p-tag value="inactive" severity="warn" /> }
                </div>
                @if (isAdmin()) {
                  <div class="card-actions">
                    <button pButton icon="pi pi-pencil" class="p-button-text p-button-rounded p-button-sm"
                            (click)="openEditDataSource(ds)" pTooltip="Edit"></button>
                    <button pButton icon="pi pi-trash" class="p-button-text p-button-rounded p-button-sm p-button-danger"
                            (click)="deleteDataSource(ds)" pTooltip="Deactivate"></button>
                  </div>
                }
              </div>
              <div class="card-detail">
                <span class="detail-label">Connection</span>
                <code class="conn-string">{{ connectionSummary(ds) }}</code>
              </div>
              <div class="meta-row">
                @if (ds.connection_config['readonly_user'] || ds.connection_config['user']) {
                  <span class="meta-badge">user: {{ ds.connection_config['readonly_user'] || ds.connection_config['user'] }}</span>
                }
                <span class="meta-badge" [class.accent]="ds.has_secrets">
                  {{ ds.has_secrets ? 'password set' : 'no password' }}
                </span>
              </div>
              @if (isAdmin()) {
                <div class="test-row">
                  <button pButton label="Test" icon="pi pi-bolt" class="p-button-sm p-button-outlined"
                          (click)="testStoredDataSource(ds)" [loading]="testingId() === ds.id"></button>
                  @if (testResults()[dsResultKey(ds.id)]; as result) {
                    <span class="test-result" [class.ok]="result.ok" [class.fail]="!result.ok">
                      @if (result.ok) { ✓ {{ result.latency_ms }}ms — {{ result.server_version }} }
                      @else { ✗ {{ result.error }} }
                    </span>
                  }
                </div>
              }
            </div>
          }
          @if (dataSources().length === 0) {
            <div class="empty-state glass-card">
              <i class="pi pi-database"></i>
              <h3>No data sources</h3>
              <p>Without one, SQL tools fall back to the server's environment connection.</p>
            </div>
          }
        </div>
      }

      <!-- ===================== EXTERNAL SERVICES ===================== -->
      @if (activeTab() === 'services') {
        <div class="cards-grid">
          @for (svc of services(); track svc.service) {
            <div class="item-card glass-card">
              <div class="card-header">
                <div class="card-title">
                  <span class="card-name">{{ svc.label }}</span>
                  @if (svc.configured && svc.source === 'db') { <p-tag value="configured" severity="success" /> }
                  @if (svc.configured && svc.source === 'env') { <p-tag value="env fallback" severity="info" /> }
                  @if (!svc.configured) { <p-tag value="not configured" severity="danger" /> }
                </div>
              </div>
              <div class="card-detail">
                <span class="detail-label">Service key</span>
                <code class="conn-string">{{ svc.service }}</code>
              </div>
              @if (svc.hint) {
                <div class="meta-row"><span class="meta-badge">key {{ svc.hint }}</span></div>
              }
              @if (objectKeys(svc.metadata).length) {
                <div class="meta-row">
                  @for (k of objectKeys(svc.metadata); track k) {
                    <span class="meta-badge">{{ k }}={{ svc.metadata[k] }}</span>
                  }
                </div>
              }
              @if (!svc.configured) {
                <p class="warn-note">
                  <i class="pi pi-exclamation-triangle"></i>
                  @if (toolsGatedBy(svc.service).length) {
                    Disabled until configured: {{ toolsGatedBy(svc.service).join(', ') }}
                  } @else {
                    Agent tools depending on this service are disabled until it is configured.
                  }
                </p>
              }
              @if (isAdmin()) {
                <div class="test-row">
                  <button pButton label="Configure" icon="pi pi-pencil" class="p-button-sm p-button-outlined"
                          (click)="openConfigureService(svc)"></button>
                  @if (svc.configured) {
                    <button pButton label="Test" icon="pi pi-bolt" class="p-button-sm p-button-outlined"
                            (click)="testService(svc)" [loading]="testingService() === svc.service"></button>
                  }
                  @if (svc.source === 'db') {
                    <button pButton label="Remove" icon="pi pi-trash" class="p-button-sm p-button-outlined p-button-danger"
                            (click)="removeService(svc)"></button>
                  }
                  @if (testResults()[svc.service]; as result) {
                    <span class="test-result" [class.ok]="result.ok" [class.fail]="!result.ok">
                      {{ result.ok ? '✓ Connected' : '✗ ' + result.error }}
                    </span>
                  }
                </div>
              }
            </div>
          }
        </div>
      }
    </div>

    <!-- Data source dialog -->
    <p-dialog [header]="editingDataSourceId() == null ? 'Add Data Source' : 'Edit Data Source'"
              [(visible)]="dataSourceDialog" [modal]="true"
              [style]="{ width: '640px', maxHeight: '85vh' }" [contentStyle]="{ overflow: 'auto' }">
      <div class="edit-form">
        <div class="form-row">
          <div class="form-field"><label>Name</label>
            <input pInputText [(ngModel)]="dsForm.name" placeholder="warehouse" /></div>
          <div class="form-field"><label>Type</label>
            <select [(ngModel)]="dsForm.db_type" class="form-select">
              @for (t of dbTypes; track t) { <option [value]="t">{{ t }}</option> }
            </select></div>
        </div>
        <div class="form-row">
          <div class="form-field"><label>Host</label>
            <input pInputText [(ngModel)]="dsForm.host" placeholder="gp.internal" /></div>
          <div class="form-field"><label>Port</label>
            <input pInputText [(ngModel)]="dsForm.port" placeholder="5432" /></div>
        </div>
        <div class="form-field"><label>Database</label>
          <input pInputText [(ngModel)]="dsForm.dbname" placeholder="analytics" /></div>
        <div class="form-row">
          <div class="form-field"><label>Read-only user</label>
            <input pInputText [(ngModel)]="dsForm.readonly_user" placeholder="readonly" /></div>
          <div class="form-field"><label>Read-only password</label>
            <input pInputText type="password" [(ngModel)]="dsForm.readonly_password"
                   [placeholder]="editingHasSecrets() ? '•••• (unchanged)' : ''" /></div>
        </div>
        @if (dialogError()) { <p class="error-text">{{ dialogError() }}</p> }
        @if (dialogTestResult(); as result) {
          <p class="test-result" [class.ok]="result.ok" [class.fail]="!result.ok">
            @if (result.ok) { ✓ Connected in {{ result.latency_ms }}ms — {{ result.server_version }} }
            @else { ✗ {{ result.error }} }
          </p>
        }
      </div>
      <ng-template pTemplate="footer">
        <button pButton label="Test connection" icon="pi pi-bolt" class="p-button-outlined"
                (click)="testDialogDataSource()" [loading]="dialogTesting()"></button>
        <button pButton label="Cancel" class="p-button-text" (click)="dataSourceDialog = false"></button>
        <button pButton label="Save" icon="pi pi-check" (click)="saveDataSource()" [loading]="saving()"></button>
      </ng-template>
    </p-dialog>

    <!-- Service credentials dialog -->
    <p-dialog [header]="'Configure ' + (configuringService()?.label || '')"
              [(visible)]="serviceDialog" [modal]="true"
              [style]="{ width: '560px' }" [contentStyle]="{ overflow: 'auto' }">
      <div class="edit-form">
        @for (f of configuringService()?.secret_fields || []; track f) {
          <div class="form-field"><label>{{ f }} <span class="secret-mark">(secret)</span></label>
            <input pInputText type="password" [(ngModel)]="serviceForm[f]"
                   [placeholder]="configuringService()?.source === 'db' ? '•••• (enter to replace)' : ''" />
          </div>
        }
        @for (f of configuringService()?.metadata_fields || []; track f) {
          <div class="form-field"><label>{{ f }}</label>
            <input pInputText [(ngModel)]="serviceForm[f]" />
          </div>
        }
        @if (dialogError()) { <p class="error-text">{{ dialogError() }}</p> }
      </div>
      <ng-template pTemplate="footer">
        <button pButton label="Cancel" class="p-button-text" (click)="serviceDialog = false"></button>
        <button pButton label="Save" icon="pi pi-check" (click)="saveService()" [loading]="saving()"></button>
      </ng-template>
    </p-dialog>
  `,
  styles: [`
    .integrations-settings { padding: var(--spacing-6); }
    .page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: var(--spacing-5); }
    .page-header h1 { font-size: var(--font-size-2xl); font-weight: 700; color: var(--surface-800); margin: 0 0 4px 0; }
    .page-header p { font-size: var(--font-size-sm); color: var(--surface-500); margin: 0; }
    .header-actions { display: flex; gap: var(--spacing-2); }
    .type-tabs { display: flex; gap: var(--spacing-2); margin-bottom: var(--spacing-5); flex-wrap: wrap; }
    .type-tab { display: flex; align-items: center; gap: var(--spacing-2); padding: 8px 16px; background: var(--surface-0); border: 1px solid var(--surface-200); border-radius: 20px; font-size: var(--font-size-sm); font-weight: 500; color: var(--surface-600); cursor: pointer; transition: all 0.2s ease; }
    .type-tab:hover { border-color: var(--primary-300); color: var(--primary-700); }
    .type-tab.active { background: var(--primary-700); border-color: var(--primary-700); color: white; }
    .type-tab.active .tab-count { background: rgba(255,255,255,0.2); color: white; }
    .tab-count { background: var(--surface-100); color: var(--surface-600); padding: 2px 8px; border-radius: 10px; font-size: var(--font-size-xs); font-weight: 600; }
    .cards-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: var(--spacing-4); }
    .item-card { padding: var(--spacing-5); transition: transform 0.2s ease, box-shadow 0.2s ease; }
    .item-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.08); }
    .item-card.inactive { opacity: 0.6; }
    .card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: var(--spacing-3); }
    .card-title { display: flex; align-items: center; gap: var(--spacing-2); flex-wrap: wrap; }
    .card-name { font-weight: 600; color: var(--surface-800); }
    .card-actions { display: flex; gap: var(--spacing-1); flex-shrink: 0; }
    .type-badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: var(--font-size-xs); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; background: #dbeafe; color: #1d4ed8; }
    .card-detail { margin-bottom: var(--spacing-3); }
    .detail-label { font-size: var(--font-size-xs); font-weight: 600; color: var(--surface-500); text-transform: uppercase; letter-spacing: 0.5px; display: block; margin-bottom: 4px; }
    .conn-string { display: inline-block; padding: 3px 10px; background: var(--surface-100); border-radius: 6px; font-size: var(--font-size-sm); color: var(--primary-700); word-break: break-all; }
    .meta-row { display: flex; gap: var(--spacing-2); flex-wrap: wrap; margin-bottom: var(--spacing-2); }
    .meta-badge { display: inline-block; padding: 2px 8px; background: var(--surface-100); color: var(--surface-600); border-radius: 4px; font-size: var(--font-size-xs); font-family: monospace; }
    .meta-badge.accent { background: var(--primary-100); color: var(--primary-700); }
    .warn-note { display: flex; align-items: center; gap: var(--spacing-2); font-size: var(--font-size-xs); color: var(--warning-color, #f59e0b); margin: 0 0 var(--spacing-2) 0; }
    .test-row { display: flex; align-items: center; gap: var(--spacing-3); flex-wrap: wrap; margin-top: var(--spacing-2); }
    .test-result { font-size: var(--font-size-xs); font-family: monospace; word-break: break-word; }
    .test-result.ok { color: var(--success-color, #10b981); }
    .test-result.fail { color: var(--error-color, #ef4444); }
    .empty-state { grid-column: 1 / -1; display: flex; flex-direction: column; align-items: center; padding: var(--spacing-8); text-align: center; }
    .empty-state i { font-size: 3rem; color: var(--surface-300); margin-bottom: var(--spacing-4); }
    .empty-state p { color: var(--surface-500); font-size: var(--font-size-sm); }
    .edit-form { display: flex; flex-direction: column; gap: var(--spacing-4); }
    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: var(--spacing-4); }
    .form-field { display: flex; flex-direction: column; gap: var(--spacing-2); }
    .form-field label { font-size: var(--font-size-sm); font-weight: 600; color: var(--surface-700); }
    .form-field input { width: 100%; }
    .form-select { padding: 10px 12px; border: 1px solid var(--surface-300); border-radius: 8px; font-size: var(--font-size-sm); color: var(--surface-700); background: var(--surface-0); outline: none; }
    .form-select:focus { border-color: var(--primary-500); box-shadow: 0 0 0 2px rgba(124,58,237,0.1); }
    .secret-mark { font-weight: 400; color: var(--surface-400); font-size: var(--font-size-xs); }
    .error-text { color: var(--error-color, #ef4444); font-size: var(--font-size-sm); margin: 0; white-space: pre-wrap; }
  `]
})
export class IntegrationsSettingsComponent implements OnInit {
  private integrations = inject(IntegrationsService);
  private auth = inject(AuthService);

  dbTypes = DB_TYPES;

  activeTab = signal<Tab>('datasources');
  saving = signal(false);
  testingId = signal<number | null>(null);
  testingService = signal<string | null>(null);
  dialogTesting = signal(false);
  dialogError = signal('');
  dialogTestResult = signal<TestResult | null>(null);
  testResults = signal<Record<string, TestResult>>({});

  services = this.integrations.services;
  dataSources = this.integrations.dataSources;
  loading = this.integrations.isLoading;
  isAdmin = this.auth.isAdmin;
  configuredServiceCount = computed(() => this.services().filter(s => s.configured).length);

  dataSourceDialog = false;
  editingDataSourceId = signal<number | null>(null);
  editingHasSecrets = signal(false);
  dsForm = this.emptyDsForm();

  serviceDialog = false;
  configuringService = signal<ServiceStatus | null>(null);
  serviceForm: Record<string, string> = {};

  ngOnInit(): void {
    this.reload();
  }

  reload(): Promise<void> {
    return this.integrations.loadAll();
  }

  objectKeys(o: Record<string, any> | undefined): string[] { return o ? Object.keys(o) : []; }

  toolsGatedBy(service: string): string[] { return this.integrations.toolsGatedBy(service); }

  connectionSummary(ds: DataSource): string {
    const c = ds.connection_config || {};
    return `${c['host'] || '?'}:${c['port'] || '?'}/${c['dbname'] || '?'}`;
  }

  /** Distinct result-map key for data sources so ids never collide with service names. */
  dsResultKey(id: number): string { return `ds:${id}`; }

  private setTestResult(key: string, result: TestResult): void {
    this.testResults.update(m => ({ ...m, [key]: result }));
  }

  // ==================== Data sources ====================

  private emptyDsForm() {
    return {
      name: '', db_type: 'greenplum', host: '', port: '5432',
      dbname: '', readonly_user: '', readonly_password: '',
    };
  }

  openAddDataSource(): void {
    this.editingDataSourceId.set(null);
    this.editingHasSecrets.set(false);
    this.dsForm = this.emptyDsForm();
    this.dialogError.set('');
    this.dialogTestResult.set(null);
    this.dataSourceDialog = true;
  }

  openEditDataSource(ds: DataSource): void {
    const c = ds.connection_config || {};
    this.editingDataSourceId.set(ds.id);
    this.editingHasSecrets.set(ds.has_secrets);
    this.dsForm = {
      name: ds.name, db_type: ds.db_type,
      host: c['host'] || '', port: String(c['port'] || '5432'),
      dbname: c['dbname'] || '', readonly_user: c['readonly_user'] || c['user'] || '',
      readonly_password: '',
    };
    this.dialogError.set('');
    this.dialogTestResult.set(null);
    this.dataSourceDialog = true;
  }

  private dsPayload(): DataSourcePayload {
    const f = this.dsForm;
    return {
      name: f.name.trim() || 'default',
      db_type: f.db_type,
      connection_config: {
        host: f.host.trim(), port: Number(f.port) || 5432,
        dbname: f.dbname.trim(), readonly_user: f.readonly_user.trim(),
      },
      // Empty password on edit = keep the stored secret unchanged
      secrets: f.readonly_password ? { readonly_password: f.readonly_password } : undefined,
      is_active: true,
    };
  }

  async testDialogDataSource(): Promise<void> {
    this.dialogTesting.set(true);
    this.dialogTestResult.set(null);
    try {
      const payload = this.dsPayload();
      const id = this.editingDataSourceId();
      // Pre-save test needs the secret; without a new one, test the stored row.
      const result = (!payload.secrets && id != null)
        ? await this.integrations.testDataSource(id)
        : await this.integrations.testDataSourceConfig(payload);
      this.dialogTestResult.set(result);
    } finally {
      this.dialogTesting.set(false);
    }
  }

  async saveDataSource(): Promise<void> {
    if (!this.dsForm.host.trim() || !this.dsForm.dbname.trim()) {
      this.dialogError.set('Host and database are required');
      return;
    }
    this.saving.set(true);
    try {
      const res = await this.integrations.saveDataSource(
        this.dsPayload(), this.editingDataSourceId() ?? undefined
      );
      if (res.success) this.dataSourceDialog = false;
      else this.dialogError.set(res.error || 'Save failed');
    } finally {
      this.saving.set(false);
    }
  }

  async deleteDataSource(ds: DataSource): Promise<void> {
    if (!confirm(`Deactivate data source '${ds.name}'?`)) return;
    await this.integrations.deleteDataSource(ds.id);
  }

  async testStoredDataSource(ds: DataSource): Promise<void> {
    this.testingId.set(ds.id);
    try {
      this.setTestResult(this.dsResultKey(ds.id), await this.integrations.testDataSource(ds.id));
    } finally {
      this.testingId.set(null);
    }
  }

  // ==================== External services ====================

  openConfigureService(svc: ServiceStatus): void {
    this.configuringService.set(svc);
    this.serviceForm = {};
    for (const f of svc.metadata_fields) {
      this.serviceForm[f] = svc.metadata[f] || '';
    }
    this.dialogError.set('');
    this.serviceDialog = true;
  }

  async saveService(): Promise<void> {
    const svc = this.configuringService();
    if (!svc) return;
    const secrets: Record<string, string> = {};
    const metadata: Record<string, string> = {};
    for (const f of svc.secret_fields) {
      if (this.serviceForm[f]) secrets[f] = this.serviceForm[f];
    }
    for (const f of svc.metadata_fields) {
      if (this.serviceForm[f]) metadata[f] = this.serviceForm[f];
    }
    this.saving.set(true);
    try {
      const res = await this.integrations.saveService(svc.service, secrets, metadata);
      if (res.success) this.serviceDialog = false;
      else this.dialogError.set(res.error || 'Save failed');
    } finally {
      this.saving.set(false);
    }
  }

  async removeService(svc: ServiceStatus): Promise<void> {
    if (!confirm(`Remove stored credentials for '${svc.label}'?`)) return;
    await this.integrations.deleteService(svc.service);
  }

  async testService(svc: ServiceStatus): Promise<void> {
    this.testingService.set(svc.service);
    try {
      this.setTestResult(svc.service, await this.integrations.testService(svc.service));
    } finally {
      this.testingService.set(null);
    }
  }
}
