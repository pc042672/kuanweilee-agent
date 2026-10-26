# Frontend Design System

Purple-themed design system integrated with PrimeNG v19.

## Design Tokens

All tokens defined in `src/styles.scss`:

| Token Type | Example | Usage |
|------------|---------|-------|
| **Primary** | `--primary-700: #7c3aed` | Main purple color |
| **Surface** | `--surface-100: #f4f4f5` | Backgrounds, borders |
| **Spacing** | `--spacing-4: 1rem` | Padding, margins, gaps |
| **Radius** | `--border-radius-md: 0.5rem` | Border radius |
| **Shadow** | `--shadow-md` | Box shadows |
| **Font** | `--font-size-sm: 0.875rem` | Typography |

## Color Palette

```
Primary (Purple):  #7c3aed (700) | #a855f7 (500) | #faf5ff (50)
Surface (Zinc):    #18181b (900) | #71717a (500) | #f4f4f5 (100)
Semantic:          Success #10b981 | Warning #f59e0b | Danger #ef4444
```

## Typography

- **Font**: Plus Jakarta Sans (Google Fonts)
- **Weights**: 400 (normal), 500 (medium), 600 (semibold), 700 (bold)
- **Sizes**: xs (0.75rem) | sm (0.875rem) | base (1rem) | lg (1.125rem)

## PrimeNG Integration

PrimeNG Aura theme colors are overridden via CSS variables:
```scss
--p-primary-700: var(--primary-700);  // Purple instead of emerald
--p-font-family: var(--font-family);
```

## Usage in Components

```scss
// Instead of hardcoded values:
padding: 12px 16px;
gap: 8px;
border-radius: 8px;

// Use design tokens:
padding: var(--spacing-3) var(--spacing-4);
gap: var(--spacing-2);
border-radius: var(--border-radius-md);
```

## Files

| File | Purpose |
|------|---------|
| `src/styles.scss` | Design tokens + PrimeNG overrides |
| `src/index.html` | Google Fonts import |
| `design-system.html` | Visual reference guide |

## Visual Reference

Open `design-system.html` in a browser to see the complete design system with live examples.
