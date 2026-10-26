# Frontend Design System (AICDP)

## 🎯 Design Principles
- **Aesthetics**: Monica AI inspired (Clean, Purple-themed, Glassmorphism).
- **Philosophy**: Minimalist, Strong Visual Hierarchy, Soft Gradients.
- **Core**: Functionality meets premium visual experience.

## 🎨 Color System

| Category | Variable | Hex | Usage |
| :--- | :--- | :--- | :--- |
| **Primary** | `--primary-color` | `#7c3aed` | Main actions, active states, focus rings |
| | `--primary-dark` | `#6d28d9` | Hover states |
| | `--primary-light` | `#a78bfa` | Accents, borders |
| | `--accent-color` | `#c4b5fd` | Subtle highlights |
| **Surface** | `--surface-0` | `#ffffff` | Card backgrounds |
| | `--surface-50` | `#fafafa` | Section backgrounds |
| | `--surface-100` | `#f4f4f5` | Hover backgrounds |
| | `--surface-200` | `#e4e4e7` | Borders |
| **Text** | `--text-color` | `#3f3f46` | Primary text |
| | `--text-color-secondary` | `#71717a` | Secondary text |
| **State** | `--error-color` | `#ef4444` | Errors, Danger actions |
| | `--success-color` | `#10b981` | Success states, KPIs |
| | `--warning-color` | `#f59e0b` | Warnings, Paused states |
| | `--info-color` | `#3b82f6` | Information, Click rates |

## 📐 Layout & Typography

### Global Styles
- **Font**: "Plus Jakarta Sans", Inter, sans-serif.
- **Background**: 
  - Base: `linear-gradient(180deg, #fafaff 0%, #fcfcff 25%, #ffffff 50%, #fcfbff 75%, #f9f8ff 100%)`
  - Overlay: `radial-gradient` (3 layers) for subtle depth.
- **Container**: Max-width `1200px` (Standard) or `1400px` (Wide). Centered.

### Spacing & Radius
- **Radius**: `--border-radius` (12px), `--border-radius-lg` (16px).
- **Spacing**: `8px` (xs), `12px` (sm), `16px` (md), `24px` (lg), `32px` (xl).

## 📦 Components

### 1. Buttons & Actions
| Class | Description | Usage |
| :--- | :--- | :--- |
| `.p-button-primary` | Solid purple, shadow | Main CTA (Submit, Next) |
| `.p-button-secondary` | Transparent, border | Secondary actions (Cancel, Back) |
| `.chip-btn` | Rounded pill, glassmorphism | Header actions, filters |
| `.btn-icon` | Square, icon-only | Toolbar actions, Edit/Delete |

### 2. Forms & Inputs
- **Style**: Glassmorphism background (`rgba(255, 255, 255, 0.8)`), blur effect.
- **Focus**: White background, `--primary-color` border, purple ring shadow.
- **Classes**:
  - `.p-inputtext`, `.input`, `.select`: Standard inputs.
  - `.p-inputgroup`: Input with attached button/icon.
  - `.p-inputswitch`: Toggle switch (Purple when active).
  - `.p-dropdown`: Custom styled dropdown.

### 3. Cards & Containers
- **Standard Card** (`.card`, `.p-card`):
  - White background, `--shadow-lg`.
  - **Shimmer Effect**: Top border gradient animation (`shimmer` keyframe).
- **Collapsible Card** (`.email-settings-card`):
  - Gradient header, expandable content area.
- **KPI Card** (`.kpi`):
  - Icon (left), Label/Value/Desc (right).
  - Hover: Lift up (`translateY(-2px)`), scale icon.

### 4. Navigation
- **Steps** (`.p-steps`):
  - Numbered circle + Title.
  - Active: Purple background, shadow ring.
  - Connected by lines.
- **Pagination** (`.pagination`):
  - Centered number list.
  - Active: Purple text, light purple bg.

### 5. Data Display
- **Data Table** (`.p-datatable`):
  - Gradient header background.
  - Hover effects on rows.
  - Status Badges: `.status-active` (Green), `.status-paused` (Orange).
- **Charts**: SVG-based, responsive containers.

## ✨ Animations
- **`hue-slide`**: 6s infinite alternate. Used on Page Titles (Text Gradient).
- **`shimmer`**: 3s linear infinite. Used on Card top borders.
- **Transitions**: All interactive elements use `0.2s ease`.

## 🤖 AI EDM Module Summary

### Overview
A comprehensive EDM campaign management system featuring AI-assisted content generation, smart scheduling, and real-time analytics.

### File Structure
- **Dashboard**: `campaign-edm.html` (KPIs, List, Charts).
- **Step 1 (Setup)**: `campaign-edm-1.html` (Schedule, Template).
- **Step 2 (Audience)**: `campaign-edm-2.html` (Segments, AI Recs).
- **Step 3 (Content)**: `campaign-edm-3.html` (CKEditor, AI Chat, Preview).
- **Step 4 (Tracking)**: `campaign-edm-5.html` (Tracking Controls).

### Technical Stack
- **Core**: Vanilla HTML5, CSS3 (Variables, Grid/Flex), ES6+ JavaScript.
- **External**: CKEditor 5 (Rich Text), Google Fonts.
- **Icons**: SVG (Inline).

---
*Retair Frontend Team • v3.0 • 2025*