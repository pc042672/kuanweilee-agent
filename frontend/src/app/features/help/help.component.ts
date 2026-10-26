import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ButtonModule } from 'primeng/button';

@Component({
  selector: 'app-help',
  standalone: true,
  imports: [CommonModule, ButtonModule],
  template: `
    <div class="help-container">
      <div class="help-content glass-card">
        <div class="help-header">
          <i class="pi pi-question-circle"></i>
          <h1>Help & Support</h1>
        </div>

        <div class="help-sections">
          <section class="help-section">
            <h2>Getting Started</h2>
            <p>AICDP is an AI-powered Customer Data Platform that helps you query and analyze your data using natural language.</p>
            <ul>
              <li><strong>Workspace:</strong> Chat with AI to query your database, generate reports, and create execution plans.</li>
              <li><strong>Plans:</strong> View and manage your saved execution plans.</li>
              <li><strong>Settings:</strong> Configure your database ontology and label rules.</li>
            </ul>
          </section>

          <section class="help-section">
            <h2>Quick Tips</h2>
            <ul>
              <li>Start a new chat in Workspace to ask questions about your data.</li>
              <li>Save useful queries to Plans for later reference.</li>
              <li>Configure your ontology in Settings to improve AI understanding of your data model.</li>
            </ul>
          </section>

          <section class="help-section">
            <h2>Need More Help?</h2>
            <p>Contact your administrator or check the documentation for more detailed guides.</p>
          </section>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .help-container {
      padding: var(--spacing-6);
      max-width: 800px;
      margin: 0 auto;
    }

    .help-content {
      padding: var(--spacing-6);
    }

    .help-header {
      display: flex;
      align-items: center;
      gap: var(--spacing-4);
      margin-bottom: var(--spacing-6);
      padding-bottom: var(--spacing-4);
      border-bottom: 1px solid var(--surface-200);

      i {
        font-size: 2.5rem;
        color: var(--primary-600);
      }

      h1 {
        font-size: var(--font-size-2xl);
        font-weight: var(--font-weight-bold);
        color: var(--surface-800);
        margin: 0;
      }
    }

    .help-sections {
      display: flex;
      flex-direction: column;
      gap: var(--spacing-6);
    }

    .help-section {
      h2 {
        font-size: var(--font-size-lg);
        font-weight: var(--font-weight-semibold);
        color: var(--surface-700);
        margin: 0 0 var(--spacing-3) 0;
      }

      p {
        font-size: var(--font-size-sm);
        color: var(--surface-600);
        margin: 0 0 var(--spacing-3) 0;
        line-height: 1.6;
      }

      ul {
        margin: 0;
        padding-left: var(--spacing-5);

        li {
          font-size: var(--font-size-sm);
          color: var(--surface-600);
          margin-bottom: var(--spacing-2);
          line-height: 1.6;

          strong {
            color: var(--surface-700);
          }
        }
      }
    }
  `]
})
export class HelpComponent {}
