import { Injectable, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

// ==================== Ontology (structure) ====================

export interface TaxonomyOption {
  name: string;
  value: string;
  semanticDefinition?: string;
  metadata?: Record<string, any>;
}

export interface ValueMapping {
  name: string;
  value: string;
  semanticDefinition?: string;
}

export interface QuizOption {
  id: string;
  text: string;
  mappings: Record<string, number>;
  nextQuestionId?: string;
}

export interface QuizQuestion {
  id: string;
  text: string;
  options: QuizOption[];
}

export interface QuizScoring {
  primaryThreshold: number;
  secondaryThreshold: number;
  maxPrimary: number;
  maxSecondary: number;
}

export interface QuizSection {
  questions: QuizQuestion[];
  scoring: QuizScoring;
}

export interface SegmentCondition {
  attribute: string;
  operator: string;
  value: any;
  secondValue?: any;
  minScore?: number;
}

export interface ColumnDef {
  dataType?: string;
  description?: string;
  businessTerm?: string;
}

/** Unified ontology node — STRUCTURE only (datasource | attribute | segment). */
export interface OntologyNode {
  type: string;
  status?: string;
  name: string;
  description?: string;
  // datasource
  table?: string;
  primaryKey?: string;
  columns?: Record<string, ColumnDef>;
  // attribute
  valueType?: string;
  isMultiple?: boolean;
  isScored?: boolean;
  options?: TaxonomyOption[];
  // segment
  conditions?: SegmentCondition[];
  logic?: string;
}

export interface UnifiedOntology {
  version: string;
  site_id: string;
  nodes: Record<string, OntologyNode>;
}

// ==================== Rules (compute) ====================

export interface SourceRef {
  datasource: string;
  column: string;
}

export interface ComputeRule {
  attribute: string;
  type: string; // sql | quiz | labeling_rule
  sources?: SourceRef[];
  sql?: string;
  quiz?: QuizSection;
  valueMappings?: ValueMapping[];
}

export interface RulesConfig {
  version: string;
  site_id: string;
  computeRules: ComputeRule[];
}

// ==================== Strategies (action) ====================

export interface Strategy {
  key: string;
  name?: string;
  segment: string;
  strategy?: string;
  template?: string;
  params?: Record<string, any>;
}

export interface StrategiesConfig {
  version: string;
  site_id: string;
  strategies: Strategy[];
}

// ==================== Scoring / resolution results ====================

export interface ScoreResult {
  attribute_key: string;
  primary: Array<{ value: string; score: number; name: string }>;
  secondary: Array<{ value: string; score: number; name: string }>;
  all_scores: Record<string, number>;
}

export interface ScoreContributionInput {
  source: string;
  points: Record<string, number>;
}

export interface SegmentMatchResult {
  site_id: string;
  ontology_version: string;
  matched: Array<{
    key: string;
    name: string;
    description?: string;
    reasoning: string[];
    strategies?: string[];
  }>;
  total_segments_evaluated: number;
}


@Injectable({ providedIn: 'root' })
export class ConfigService {
  private readonly API_BASE = '';
  private readonly ONTOLOGY_V2_KEY = 'aicdp_ontology_v2';

  private http = inject(HttpClient);
  private ontologyV2 = signal<UnifiedOntology | null>(null);
  private rules = signal<RulesConfig | null>(null);
  private strategiesCfg = signal<StrategiesConfig | null>(null);
  private loading = signal(false);

  isLoading() {
    return this.loading.asReadonly();
  }

  getOntologyV2() {
    return this.ontologyV2.asReadonly();
  }

  getRules() {
    return this.rules.asReadonly();
  }

  getStrategies() {
    return this.strategiesCfg.asReadonly();
  }

  // ==================== Ontology (structure) ====================

  async loadOntologyV2(): Promise<UnifiedOntology | null> {
    try {
      const response = await firstValueFrom(
        this.http.get<UnifiedOntology>(`${this.API_BASE}/api/ontology`)
      );
      this.ontologyV2.set(response);
      localStorage.setItem(this.ONTOLOGY_V2_KEY, JSON.stringify(response));
      return response;
    } catch (e) {
      console.warn('Failed to load ontology:', e);
      const cached = localStorage.getItem(this.ONTOLOGY_V2_KEY);
      if (cached) {
        const parsed = JSON.parse(cached) as UnifiedOntology;
        this.ontologyV2.set(parsed);
        return parsed;
      }
      return null;
    }
  }

  async getOntologyV2Nodes(type?: string): Promise<Record<string, OntologyNode>> {
    const params = type ? `?type=${type}` : '';
    return firstValueFrom(
      this.http.get<Record<string, OntologyNode>>(`${this.API_BASE}/api/ontology/nodes${params}`)
    );
  }

  async createOntologyNode(key: string, node: OntologyNode): Promise<boolean> {
    try {
      await firstValueFrom(this.http.post(`${this.API_BASE}/api/ontology/nodes/${key}`, node));
      await this.loadOntologyV2();
      return true;
    } catch (e) {
      console.error('Failed to create ontology node:', e);
      return false;
    }
  }

  async updateOntologyNode(key: string, node: OntologyNode): Promise<boolean> {
    try {
      await firstValueFrom(this.http.put(`${this.API_BASE}/api/ontology/nodes/${key}`, node));
      await this.loadOntologyV2();
      return true;
    } catch (e) {
      console.error('Failed to update ontology node:', e);
      return false;
    }
  }

  async deleteOntologyNode(key: string): Promise<boolean> {
    try {
      await firstValueFrom(this.http.delete(`${this.API_BASE}/api/ontology/nodes/${key}`));
      await this.loadOntologyV2();
      return true;
    } catch (e) {
      console.error('Failed to delete ontology node:', e);
      return false;
    }
  }

  // ==================== Rules (compute) ====================

  async loadRules(): Promise<RulesConfig | null> {
    try {
      const response = await firstValueFrom(
        this.http.get<RulesConfig>(`${this.API_BASE}/api/ontology/rules`)
      );
      this.rules.set(response);
      return response;
    } catch (e) {
      console.warn('Failed to load rules:', e);
      return null;
    }
  }

  async saveRules(config: RulesConfig): Promise<{ success: boolean; error?: string }> {
    try {
      await firstValueFrom(this.http.put(`${this.API_BASE}/api/ontology/rules`, config));
      await this.loadRules();
      return { success: true };
    } catch (e: any) {
      const detail = e?.error?.detail || e?.message || 'Save failed';
      console.error('Failed to save rules:', detail);
      return { success: false, error: String(detail) };
    }
  }

  // ==================== Strategies (action) ====================

  async loadStrategies(): Promise<StrategiesConfig | null> {
    try {
      const response = await firstValueFrom(
        this.http.get<StrategiesConfig>(`${this.API_BASE}/api/ontology/strategies`)
      );
      this.strategiesCfg.set(response);
      return response;
    } catch (e) {
      console.warn('Failed to load strategies:', e);
      return null;
    }
  }

  async saveStrategies(config: StrategiesConfig): Promise<{ success: boolean; error?: string }> {
    try {
      await firstValueFrom(this.http.put(`${this.API_BASE}/api/ontology/strategies`, config));
      await this.loadStrategies();
      return { success: true };
    } catch (e: any) {
      const detail = e?.error?.detail || e?.message || 'Save failed';
      console.error('Failed to save strategies:', detail);
      return { success: false, error: String(detail) };
    }
  }

  // ==================== Scoring & resolution ====================

  async scoreQuiz(attributeKey: string, responses: Record<string, string>): Promise<ScoreResult> {
    return firstValueFrom(
      this.http.post<ScoreResult>(`${this.API_BASE}/api/ontology/nodes/${attributeKey}/score`, { responses })
    );
  }

  async labelScores(attributeKey: string, contributions: ScoreContributionInput[],
                    scoring?: { primaryThreshold: number; secondaryThreshold: number; maxPrimary: number; maxSecondary: number }): Promise<ScoreResult> {
    return firstValueFrom(
      this.http.post<ScoreResult>(`${this.API_BASE}/api/ontology/nodes/${attributeKey}/label`, { contributions, scoring })
    );
  }

  async resolveSegments(attributes: Record<string, any>): Promise<SegmentMatchResult> {
    return firstValueFrom(
      this.http.post<SegmentMatchResult>(`${this.API_BASE}/api/ontology/resolve-segments`, { attributes })
    );
  }

  async resolveStrategy(segmentKey: string, strategyKey: string, context: Record<string, any> = {}): Promise<any> {
    return firstValueFrom(
      this.http.post(`${this.API_BASE}/api/ontology/resolve-strategy`, {
        segment_key: segmentKey,
        strategy_key: strategyKey,
        context
      })
    );
  }
}
