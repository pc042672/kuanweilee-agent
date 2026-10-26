import { Component, signal, inject, computed, DestroyRef, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { InputTextarea } from 'primeng/inputtextarea';
import { DialogModule } from 'primeng/dialog';
import { TooltipModule } from 'primeng/tooltip';
import { TagModule } from 'primeng/tag';
import {
  ConfigService, UnifiedOntology, OntologyNode, RulesConfig, ComputeRule,
  StrategiesConfig, Strategy
} from '../../shared/services/config.service';

interface NodeEntry { key: string; node: OntologyNode; }
type Mode = 'structure' | 'rules' | 'strategy';

@Component({
  selector: 'app-ontology-v2-settings',
  standalone: true,
  imports: [CommonModule, FormsModule, ButtonModule, InputTextModule, InputTextarea, DialogModule, TooltipModule, TagModule],
  template: `
    <div class="ontology-v2-settings">
      <div class="page-header">
        <div>
          <h1>{{ titles[mode()] }}</h1>
          <p>{{ subtitles[mode()] }}</p>
        </div>
        <div class="header-actions">
          <button pButton label="Reload" icon="pi pi-refresh" class="p-button-outlined" (click)="reload()" [loading]="loading()"></button>
          @if (mode() === 'structure') { <button pButton label="Add Node" icon="pi pi-plus" (click)="openAddNode()"></button> }
          @if (mode() === 'rules') { <button pButton label="Edit rules.json" icon="pi pi-pencil" class="p-button-outlined" (click)="openRulesEditor()"></button> }
          @if (mode() === 'strategy') { <button pButton label="Edit strategies.json" icon="pi pi-pencil" class="p-button-outlined" (click)="openStrategiesEditor()"></button> }
        </div>
      </div>

      <!-- ===================== ONTOLOGY (structure) ===================== -->
      @if (mode() === 'structure') {
        <div class="type-tabs">
          <button class="type-tab" [class.active]="activeType() === 'all'" (click)="activeType.set('all')">All <span class="tab-count">{{ allNodes().length }}</span></button>
          @for (t of nodeTypes; track t) {
            <button class="type-tab" [class.active]="activeType() === t" (click)="activeType.set(t)">{{ t }} <span class="tab-count">{{ countByType(t) }}</span></button>
          }
        </div>
        <div class="nodes-grid">
          @for (entry of filteredNodes(); track entry.key) {
            <div class="node-card glass-card">
              <div class="node-header">
                <div class="node-title">
                  <span class="type-badge" [attr.data-type]="entry.node.type">{{ entry.node.type }}</span>
                  <span class="node-name">{{ entry.node.name }}</span>
                </div>
                <div class="node-actions">
                  <button pButton icon="pi pi-pencil" class="p-button-text p-button-rounded p-button-sm" (click)="openEditNode(entry)" pTooltip="Edit"></button>
                  <button pButton icon="pi pi-trash" class="p-button-text p-button-rounded p-button-sm p-button-danger" (click)="deleteNode(entry.key)" pTooltip="Delete"></button>
                </div>
              </div>
              <div class="node-key"><code>{{ entry.key }}</code></div>
              @if (entry.node.description) { <p class="node-description">{{ entry.node.description }}</p> }

              @if (entry.node.type === 'datasource') {
                <div class="node-detail"><span class="detail-label">Table</span> <code class="target-node">{{ entry.node.table }}</code></div>
                @if (entry.node.columns) { <div class="meta-row"><span class="meta-badge">{{ objectKeys(entry.node.columns).length }} columns</span></div> }
              }
              @if (entry.node.type === 'attribute') {
                <div class="meta-row">
                  @if (entry.node.valueType) { <span class="meta-badge">{{ entry.node.valueType }}</span> }
                  @if (entry.node.isMultiple) { <span class="meta-badge accent">Multiple</span> }
                  @if (entry.node.isScored) { <span class="meta-badge accent">Scored</span> }
                  <span class="meta-badge">{{ computeRulesFor(entry.key).length }} rule(s)</span>
                </div>
                @if (entry.node.options?.length) {
                  <div class="node-detail"><span class="detail-label">Options ({{ entry.node.options?.length }})</span>
                    <div class="options-list">@for (opt of (entry.node.options || []).slice(0, 8); track opt.value) { <span class="option-chip">{{ opt.name }} <code>{{ opt.value }}</code></span> }</div>
                  </div>
                }
              }
              @if (entry.node.type === 'segment') {
                @if (entry.node.conditions?.length) {
                  <div class="node-detail"><span class="detail-label">Conditions ({{ entry.node.logic || 'ALL' }})</span>
                    <div class="rules-list">
                      @for (c of entry.node.conditions; track $index) {
                        <div class="rule-chip"><code>{{ c.attribute }}</code><span class="operator">{{ c.operator }}</span><code>{{ c.value }}</code>@if (c.minScore != null) { <span class="meta-badge">≥{{ c.minScore }}</span> }</div>
                      }
                    </div>
                  </div>
                }
                <div class="meta-row">@for (s of strategiesForSeg(entry.key); track s.key) { <span class="meta-badge accent">{{ s.key }}</span> }</div>
              }
            </div>
          }
          @if (filteredNodes().length === 0) { <div class="empty-state glass-card"><i class="pi pi-inbox"></i><h3>No Nodes</h3></div> }
        </div>
      }

      <!-- ===================== RULES (compute) ===================== -->
      @if (mode() === 'rules') {
        <div class="nodes-grid">
          @for (r of rules()?.computeRules || []; track $index) {
            <div class="node-card glass-card">
              <div class="node-header"><div class="node-title"><span class="type-badge" [attr.data-type]="'attribute'">{{ r.type }}</span><span class="node-name">{{ r.attribute }}</span></div></div>
              @if (r.sources?.length) { <div class="node-detail"><span class="detail-label">Sources</span><div class="options-list">@for (s of r.sources; track $index) { <code class="source-chip">{{ s.datasource }}.{{ s.column }}</code> }</div></div> }
              @if (r.sql) { <pre class="sql-block"><code>{{ r.sql }}</code></pre> }
              @if (r.quiz?.questions?.length) { <div class="meta-row"><span class="meta-badge">{{ r.quiz?.questions?.length }} questions</span></div> }
            </div>
          }
          @if ((rules()?.computeRules || []).length === 0) { <div class="empty-state glass-card"><i class="pi pi-inbox"></i><h3>No compute rules</h3></div> }
        </div>
        <div class="test-panel glass-card">
          <h3>Test — score a quiz attribute</h3>
          <div class="form-field"><label>Attribute</label>
            <select [(ngModel)]="testAttribute" class="form-select"><option value="">-- select --</option>@for (a of scoredAttributes(); track a.key) { <option [value]="a.key">{{ a.node.name }} ({{ a.key }})</option> }</select>
          </div>
          <div class="form-field"><label>Responses JSON (question_id &rarr; option_id)</label><textarea pInputTextarea [(ngModel)]="testResponses" [rows]="3" class="json-textarea"></textarea></div>
          <button pButton label="Score" icon="pi pi-play" (click)="runScore()" [disabled]="!testAttribute"></button>
          @if (testResult()) { <pre class="sql-block"><code>{{ testResult() }}</code></pre> }
        </div>
      }

      <!-- ===================== STRATEGY (action) ===================== -->
      @if (mode() === 'strategy') {
        <div class="nodes-grid">
          @for (s of strategies()?.strategies || []; track $index) {
            <div class="node-card glass-card">
              <div class="node-header"><div class="node-title"><span class="type-badge" [attr.data-type]="'segment'">{{ s.key }}</span><span class="node-name">{{ s.segment }}</span></div></div>
              @if (s.strategy) { <div class="node-detail"><span class="detail-label">Strategy</span> <code class="target-node">{{ s.strategy }}</code></div> }
              @if (s.template) { <p class="node-description">{{ s.template }}</p> }
              @if (s.params && objectKeys(s.params).length) { <div class="meta-row">@for (k of objectKeys(s.params); track k) { <span class="meta-badge">{{ k }}={{ s.params?.[k] }}</span> }</div> }
            </div>
          }
          @if ((strategies()?.strategies || []).length === 0) { <div class="empty-state glass-card"><i class="pi pi-inbox"></i><h3>No strategies</h3></div> }
        </div>
        <div class="test-panel glass-card">
          <h3>Test — resolve a strategy</h3>
          <div class="form-row">
            <div class="form-field"><label>Segment</label><select [(ngModel)]="testSegment" class="form-select"><option value="">-- select --</option>@for (s of segmentNodes(); track s.key) { <option [value]="s.key">{{ s.node.name }} ({{ s.key }})</option> }</select></div>
            <div class="form-field"><label>Strategy key</label><input pInputText [(ngModel)]="testStrategyKey" placeholder="nba" /></div>
          </div>
          <div class="form-field"><label>Context JSON</label><textarea pInputTextarea [(ngModel)]="testContext" [rows]="2" class="json-textarea"></textarea></div>
          <button pButton label="Resolve" icon="pi pi-play" (click)="runResolve()" [disabled]="!testSegment || !testStrategyKey"></button>
          @if (testResult()) { <pre class="sql-block"><code>{{ testResult() }}</code></pre> }
        </div>
      }
    </div>

    <!-- Node dialog -->
    <p-dialog [header]="editMode() === 'add' ? 'Add Node' : 'Edit Node'" [(visible)]="nodeDialog" [modal]="true" [style]="{ width: '720px', maxHeight: '85vh' }" [contentStyle]="{ overflow: 'auto' }">
      <div class="edit-form">
        <div class="form-row">
          <div class="form-field"><label>Key</label><input pInputText [(ngModel)]="editNodeKey" placeholder="e.g. archetype" [disabled]="editMode() === 'edit'" /></div>
          <div class="form-field"><label>Type</label><select [(ngModel)]="editNodeType" class="form-select" [disabled]="editMode() === 'edit'" (ngModelChange)="seedJson()">@for (t of nodeTypes; track t) { <option [value]="t">{{ t }}</option> }</select></div>
        </div>
        <div class="form-field"><label>Node JSON</label><textarea pInputTextarea [(ngModel)]="nodeJson" [rows]="14" class="json-textarea" placeholder="Node JSON"></textarea></div>
        @if (dialogError()) { <p class="error-text">{{ dialogError() }}</p> }
      </div>
      <ng-template pTemplate="footer">
        <button pButton label="Cancel" class="p-button-text" (click)="nodeDialog = false"></button>
        <button pButton [label]="editMode() === 'add' ? 'Create' : 'Update'" icon="pi pi-check" (click)="saveNode()" [loading]="saving()"></button>
      </ng-template>
    </p-dialog>

    <!-- Config JSON editor dialog (rules or strategies) -->
    <p-dialog [header]="'Edit ' + jsonDialogTarget() + '.json'" [(visible)]="jsonDialog" [modal]="true" [style]="{ width: '760px', maxHeight: '85vh' }" [contentStyle]="{ overflow: 'auto' }">
      <div class="edit-form">
        <textarea pInputTextarea [(ngModel)]="configJson" [rows]="22" class="json-textarea"></textarea>
        @if (dialogError()) { <p class="error-text">{{ dialogError() }}</p> }
      </div>
      <ng-template pTemplate="footer">
        <button pButton label="Cancel" class="p-button-text" (click)="jsonDialog = false"></button>
        <button pButton label="Save" icon="pi pi-check" (click)="saveConfigJson()" [loading]="saving()"></button>
      </ng-template>
    </p-dialog>
  `,
  styles: [`
    .ontology-v2-settings { padding: var(--spacing-6); }
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
    .nodes-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: var(--spacing-4); }
    .node-card { padding: var(--spacing-5); transition: transform 0.2s ease, box-shadow 0.2s ease; }
    .node-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.08); }
    .node-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: var(--spacing-2); }
    .node-title { display: flex; align-items: center; gap: var(--spacing-2); flex-wrap: wrap; }
    .node-name { font-weight: 600; color: var(--surface-800); }
    .node-key { margin-bottom: var(--spacing-2); }
    .node-key code { font-size: var(--font-size-xs); color: var(--surface-500); }
    .node-actions { display: flex; gap: var(--spacing-1); flex-shrink: 0; }
    .type-badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: var(--font-size-xs); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; background: var(--primary-100); color: var(--primary-700); }
    .type-badge[data-type="datasource"] { background: #dbeafe; color: #1d4ed8; }
    .type-badge[data-type="attribute"] { background: #ede9fe; color: #6d28d9; }
    .type-badge[data-type="segment"] { background: #d1fae5; color: #065f46; }
    .node-description { font-size: var(--font-size-sm); color: var(--surface-600); margin: 0 0 var(--spacing-3) 0; line-height: 1.5; }
    .node-detail { margin-bottom: var(--spacing-3); }
    .detail-label { font-size: var(--font-size-xs); font-weight: 600; color: var(--surface-500); text-transform: uppercase; letter-spacing: 0.5px; display: block; margin-bottom: 4px; }
    .options-list { display: flex; flex-wrap: wrap; gap: var(--spacing-1); }
    .option-chip { display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; background: var(--surface-100); border-radius: 6px; font-size: var(--font-size-xs); color: var(--surface-700); }
    .option-chip code { color: var(--surface-500); font-size: 10px; }
    .source-chip { display: inline-block; padding: 3px 10px; background: var(--surface-800); color: #a5d6ff; border-radius: 6px; font-size: var(--font-size-xs); }
    .target-node { display: inline-block; padding: 3px 10px; background: var(--surface-100); border-radius: 6px; font-size: var(--font-size-sm); color: var(--primary-700); }
    .sql-block { background: var(--surface-800); color: #a5d6ff; border-radius: 8px; padding: 12px 16px; font-family: monospace; font-size: 11px; line-height: 1.6; overflow-x: auto; white-space: pre-wrap; word-break: break-word; margin-top: 4px; }
    .sql-block code { color: inherit; background: none; }
    .meta-row { display: flex; gap: var(--spacing-2); flex-wrap: wrap; margin-top: var(--spacing-2); }
    .meta-badge { display: inline-block; padding: 2px 8px; background: var(--surface-100); color: var(--surface-600); border-radius: 4px; font-size: var(--font-size-xs); font-family: monospace; }
    .meta-badge.accent { background: var(--primary-100); color: var(--primary-700); }
    .rules-list { display: flex; flex-direction: column; gap: var(--spacing-1); }
    .rule-chip { display: flex; align-items: center; gap: var(--spacing-2); padding: 4px 8px; background: var(--surface-50); border: 1px solid var(--surface-200); border-radius: 6px; font-size: var(--font-size-xs); }
    .rule-chip code { background: var(--surface-100); padding: 1px 4px; border-radius: 3px; }
    .rule-chip .operator { color: var(--primary-600); font-weight: 500; }
    .empty-state { grid-column: 1 / -1; display: flex; flex-direction: column; align-items: center; padding: var(--spacing-8); text-align: center; }
    .empty-state i { font-size: 3rem; color: var(--surface-300); margin-bottom: var(--spacing-4); }
    .edit-form { display: flex; flex-direction: column; gap: var(--spacing-4); }
    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: var(--spacing-4); }
    .form-field { display: flex; flex-direction: column; gap: var(--spacing-2); }
    .form-field label { font-size: var(--font-size-sm); font-weight: 600; color: var(--surface-700); }
    .form-field input, .form-field textarea, .form-field select { width: 100%; }
    .form-select { padding: 10px 12px; border: 1px solid var(--surface-300); border-radius: 8px; font-size: var(--font-size-sm); color: var(--surface-700); background: var(--surface-0); outline: none; }
    .form-select:focus { border-color: var(--primary-500); box-shadow: 0 0 0 2px rgba(124,58,237,0.1); }
    .json-textarea { font-family: monospace; font-size: var(--font-size-sm); line-height: 1.5; }
    .test-panel { padding: var(--spacing-6); display: flex; flex-direction: column; gap: var(--spacing-3); max-width: 760px; margin-top: var(--spacing-5); }
    .test-panel h3 { margin: 0; color: var(--surface-700); }
    .error-text { color: var(--error-color, #ef4444); font-size: var(--font-size-sm); margin: 0; white-space: pre-wrap; }
  `]
})
export class OntologyV2SettingsComponent implements OnInit {
  private configService = inject(ConfigService);
  private route = inject(ActivatedRoute);
  private destroyRef = inject(DestroyRef);

  nodeTypes = ['datasource', 'attribute', 'segment'];
  titles: Record<Mode, string> = { structure: 'Ontology', rules: 'Rules', strategy: 'Strategy' };
  subtitles: Record<Mode, string> = {
    structure: 'Structure — datasources, attributes, segments',
    rules: 'Compute rules — how attributes get their values',
    strategy: 'Strategies — action tunes (NBA/NBO and beyond) per segment',
  };

  mode = signal<Mode>('structure');
  activeType = signal<string>('all');
  loading = signal(false);
  saving = signal(false);

  nodeDialog = false;
  jsonDialog = false;
  jsonDialogTarget = signal<'rules' | 'strategies'>('rules');
  editMode = signal<'add' | 'edit'>('add');
  dialogError = signal<string>('');

  editNodeKey = '';
  editNodeType = 'attribute';
  nodeJson = '';
  configJson = '';

  testAttribute = '';
  testResponses = '{\n  "q1": "a"\n}';
  testSegment = '';
  testStrategyKey = 'nba';
  testContext = '{\n  "offering": "10% off"\n}';
  testResult = signal<string>('');

  ontology = this.configService.getOntologyV2();
  rules = this.configService.getRules();
  strategies = this.configService.getStrategies();

  allNodes = computed<NodeEntry[]>(() => {
    const config = this.ontology();
    return config?.nodes ? Object.entries(config.nodes).map(([key, node]) => ({ key, node })) : [];
  });
  filteredNodes = computed<NodeEntry[]>(() => {
    const type = this.activeType();
    const nodes = this.allNodes();
    return type === 'all' ? nodes : nodes.filter(e => e.node.type === type);
  });
  scoredAttributes = computed<NodeEntry[]>(() => this.allNodes().filter(e => e.node.type === 'attribute' && e.node.isScored));
  segmentNodes = computed<NodeEntry[]>(() => this.allNodes().filter(e => e.node.type === 'segment'));

  ngOnInit(): void {
    this.route.data.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(d => this.mode.set((d['mode'] as Mode) || 'structure'));
    this.reload();
  }

  objectKeys(o: Record<string, any> | undefined): string[] { return o ? Object.keys(o) : []; }
  countByType(type: string): number { return this.allNodes().filter(e => e.node.type === type).length; }
  computeRulesFor(attr: string): ComputeRule[] { return (this.rules()?.computeRules || []).filter(r => r.attribute === attr); }
  strategiesForSeg(seg: string): Strategy[] { return (this.strategies()?.strategies || []).filter(s => s.segment === seg); }

  async reload(): Promise<void> {
    this.loading.set(true);
    try {
      await Promise.all([
        this.configService.loadOntologyV2(),
        this.configService.loadRules(),
        this.configService.loadStrategies(),
      ]);
    } finally {
      this.loading.set(false);
    }
  }

  seedJson(): void {
    const seeds: Record<string, any> = {
      datasource: { type: 'datasource', name: '', description: '', table: '', columns: {} },
      attribute: { type: 'attribute', name: '', description: '', valueType: 'STR', isMultiple: false, isScored: false, options: [] },
      segment: { type: 'segment', name: '', description: '', conditions: [], logic: 'ALL' }
    };
    this.nodeJson = JSON.stringify(seeds[this.editNodeType] || {}, null, 2);
  }

  openAddNode(): void {
    this.editMode.set('add');
    this.editNodeKey = '';
    this.editNodeType = this.activeType() !== 'all' ? this.activeType() : 'attribute';
    this.dialogError.set('');
    this.seedJson();
    this.nodeDialog = true;
  }

  openEditNode(entry: NodeEntry): void {
    this.editMode.set('edit');
    this.editNodeKey = entry.key;
    this.editNodeType = entry.node.type;
    this.nodeJson = JSON.stringify(entry.node, null, 2);
    this.dialogError.set('');
    this.nodeDialog = true;
  }

  async saveNode(): Promise<void> {
    if (!this.editNodeKey.trim()) { this.dialogError.set('Key is required'); return; }
    let node: OntologyNode;
    try { node = JSON.parse(this.nodeJson); } catch (e: any) { this.dialogError.set('Invalid JSON: ' + e.message); return; }
    this.saving.set(true);
    try {
      const ok = this.editMode() === 'add'
        ? await this.configService.createOntologyNode(this.editNodeKey.trim(), node)
        : await this.configService.updateOntologyNode(this.editNodeKey.trim(), node);
      if (ok) this.nodeDialog = false; else this.dialogError.set('Save failed (backend validation)');
    } finally { this.saving.set(false); }
  }

  async deleteNode(key: string): Promise<void> {
    if (!confirm(`Delete node '${key}'?`)) return;
    await this.configService.deleteOntologyNode(key);
  }

  openRulesEditor(): void {
    this.jsonDialogTarget.set('rules');
    this.configJson = JSON.stringify(this.rules() || { version: '1.0.0', site_id: 'default', computeRules: [] }, null, 2);
    this.dialogError.set('');
    this.jsonDialog = true;
  }

  openStrategiesEditor(): void {
    this.jsonDialogTarget.set('strategies');
    this.configJson = JSON.stringify(this.strategies() || { version: '1.0.0', site_id: 'default', strategies: [] }, null, 2);
    this.dialogError.set('');
    this.jsonDialog = true;
  }

  async saveConfigJson(): Promise<void> {
    let parsed: any;
    try { parsed = JSON.parse(this.configJson); } catch (e: any) { this.dialogError.set('Invalid JSON: ' + e.message); return; }
    this.saving.set(true);
    try {
      const res = this.jsonDialogTarget() === 'rules'
        ? await this.configService.saveRules(parsed)
        : await this.configService.saveStrategies(parsed);
      if (res.success) this.jsonDialog = false; else this.dialogError.set(res.error || 'Save failed');
    } finally { this.saving.set(false); }
  }

  async runScore(): Promise<void> {
    try {
      const r = await this.configService.scoreQuiz(this.testAttribute, JSON.parse(this.testResponses));
      this.testResult.set(JSON.stringify(r, null, 2));
    } catch (e: any) { this.testResult.set('Error: ' + (e?.error?.detail || e.message)); }
  }

  async runResolve(): Promise<void> {
    try {
      const context = this.testContext.trim() ? JSON.parse(this.testContext) : {};
      const r = await this.configService.resolveStrategy(this.testSegment, this.testStrategyKey, context);
      this.testResult.set(JSON.stringify(r, null, 2));
    } catch (e: any) { this.testResult.set('Error: ' + (e?.error?.detail || e.message)); }
  }
}
