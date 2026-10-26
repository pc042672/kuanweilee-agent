# UI Guidelines

## Do NOT use emoji symbols as UI components

Avoid using emoji characters like:
- 🔄 (sync/loading)
- ⏳ (waiting)
- ⚡ (action)
- ✅ (success)
- ❌ (error)
- 🔙 (back)
- ➕ (add)

**Reason**: Emojis render inconsistently across platforms and browsers. They cannot be styled (color, size, animation) like proper icons.

**Instead use**:
- PrimeNG icons (`pi pi-check`, `pi pi-times`, `pi pi-sync`, etc.)
- SVG icons
- Icon fonts

**Example**:
```html
<!-- BAD: Emoji -->
<span>🔄 Loading...</span>

<!-- GOOD: Icon component -->
<i class="pi pi-spin pi-spinner"></i>
<span>Loading...</span>
```

This applies to both frontend templates AND backend response messages that will be displayed in the UI.

## Chat Panel UX Patterns

### Thinking Process Display

**Grouping Rule**: Consecutive tool calls should be merged into ONE "Thinking process" box. When a different content type appears (execution plan, result, verification), close the thinking box and display that content. If more tool calls happen after content, start a NEW thinking box.

```
Tool Call 1 ─┐
Tool Call 2  ├─> ONE Thinking Box
Tool Call 3 ─┘
Content Block ──> Show content, close thinking
Tool Call 4 ─┐
Tool Call 5  ├─> NEW Thinking Box
```

**Auto-expand/collapse**: 
- Auto-expand thinking process while it's active (no content after it yet)
- Auto-collapse when results/content appear after it
- User can manually toggle to override

**Deduplication**: When the same tool is called multiple times (e.g., in-progress then completed), show only ONE entry - keep the completed version with result.

### Cards and Collapsible Content

**Default states**:
- Result/Plan cards: **Open by default** (`isBlockExpanded` returns `true`)
- Thinking process: **Expanded while active**, collapsed when results appear

### Avoid Duplicate Visual Indicators

Don't show the same status with multiple visual elements:
```html
<!-- BAD: Both text ✓ and icon -->
<i class="pi pi-check"></i> Task completed ✓

<!-- GOOD: Icon only -->
<i class="pi pi-check text-green-500"></i> Task completed
```

### Empty Content Handling

Don't render message wrapper divs when there's no content to display:
```typescript
// Only render if there's actual content
@if (message.role === 'user' || (message.role === 'assistant' && getDisplayItems(message).length > 0)) {
  <div class="message">...</div>
}
```

This prevents blank spaces appearing in the chat during streaming/loading states.
