# AI-CDP Frontend Redesign Plan

## Summary
Redesign the frontend to address 4 key issues:
1. Rebrand from "iCEM" to "AICDP"
2. Move Ontology & Label Rules to a Settings area
3. Add chat history visibility with session management
4. Connect Plans and Chat with linking capability

---

## Current State Analysis

### Branding (iCEM)
Files to update:
- `src/app/core/auth/login.component.ts` - Logo heading (line 39), copyright (line 95)
- `src/app/core/layout/sidebar.component.ts` - Logo text (line 26)
- `CLAUDE.md` - Documentation title

### Settings Gap
- No settings module exists (sidebar has stub only)
- Ontology stored in `/config/ontology.json` - requires manual editing
- Labels stored in `/config/label_rules.json` - requires manual editing
- Frontend components use hardcoded mock data

### Chat Issues
- Chat component: `src/app/custom-chat.component.ts`
- No session persistence - messages lost on reload
- No history sidebar - can't see past conversations
- Uses CopilotKit with in-memory storage only

### Plan-Chat Disconnect
- Plans at `/plans` route, Chat at `/chat` route - separate silos
- No way to link chat conversation to a plan
- No way to access plan results from dialog/menu

---

## Proposed Architecture

### New Route Structure
```
/workspace                  → Main chat area with session sidebar
/workspace/chat/:sessionId  → Specific chat session
/plans                      → Plan list (enhanced with linked chats)
/plans/:id                  → Plan editor with chat panel
/settings                   → Settings overview
/settings/ontology          → Ontology editor
/settings/labels            → Label rules editor
```

### New Navigation (Sidebar)
```
Main:
  - Workspace (chat-centric, replaces hidden /chat)
  - Plans

Footer:
  - Settings (contains Ontology + Labels)
```

### Component Structure
```
features/
├── workspace/                    # NEW
│   ├── workspace.component.ts    # Split-pane: sidebar + chat
│   ├── chat-sidebar.component.ts # Session list with history
│   ├── chat-panel.component.ts   # Enhanced chat (from custom-chat)
│   ├── plan-selector.component.ts # Dropdown to select/scope to a plan
│   └── save-to-plan-dialog.component.ts
├── plans/
│   ├── plan-list.component.ts
│   └── plan-editor.component.ts  # Enhanced with linked chats panel
└── settings/                     # NEW
    ├── settings-shell.component.ts
    ├── ontology-settings.component.ts
    └── labels-settings.component.ts
```

### New Services
```
shared/services/
├── chat-session.service.ts   # Session CRUD, localStorage persistence
├── config.service.ts         # Ontology/Labels load/save via localStorage
└── plan.service.ts           # Plan CRUD with chat linking, localStorage
```

---

## Implementation Plan

### Phase 1: Branding & Settings Foundation
1. Update "iCEM" → "AICDP" in sidebar and login components
2. Create Settings shell with sub-navigation
3. Move Ontology/Labels under Settings routes
4. Create ConfigService using localStorage (no backend API for now)

### Phase 2: Config Editing
1. Enable editing in Ontology settings page (save to localStorage)
2. Enable editing in Labels settings page (save to localStorage)
3. Add JSON import/export functionality
4. Pre-populate with default config on first load

### Phase 3: Chat Persistence & History
1. Create ChatSessionService with localStorage
2. Build Workspace component with split-pane layout
3. Create chat-sidebar with session list (grouped by date)
4. Migrate custom-chat.component to chat-panel
5. Update routes to new `/workspace` structure

### Phase 4: Plan-Chat Integration
Three user flows to support:

**Flow A: New Chat → Save to Plan**
1. User starts new chat in Workspace
2. Types goal, AI generates execution plan + SQL
3. User clicks "Save to Plan" → creates new plan with this chat attached

**Flow B: Call Agent for Plan (in Chat)**
1. User types request in chat
2. AI (DS-Agent) returns structured execution plan
3. AI (DE-Agent) executes plan, returns SQL results
4. Conversation is automatically linked to generated plan

**Flow C: Select Plan → Run in Dialog**
1. In Workspace header, add "Select Plan" dropdown
2. User picks existing plan from list
3. Chat context is scoped to that plan (goal/situation pre-loaded)
4. AI uses plan context for more targeted responses

Implementation:
1. Add `chatSessionIds` field to Plan model
2. Add `planId` field to ChatSession model
3. Create PlanSelectorDropdown in Workspace header
4. Add "Save to Plan" action button in chat
5. Create PlanService with bidirectional linking

---

## Key Files to Modify

### Branding
- `src/app/core/auth/login.component.ts`
- `src/app/core/layout/sidebar.component.ts`
- `CLAUDE.md`

### Routes
- `src/app/app.routes.ts` - Add workspace, settings routes; remove ontology/labels top-level routes

### New Components
- `src/app/features/workspace/workspace.component.ts`
- `src/app/features/workspace/chat-sidebar.component.ts`
- `src/app/features/workspace/chat-panel.component.ts`
- `src/app/features/workspace/plan-selector.component.ts`
- `src/app/features/workspace/save-to-plan-dialog.component.ts`
- `src/app/features/settings/settings-shell.component.ts`
- `src/app/features/settings/ontology-settings.component.ts`
- `src/app/features/settings/labels-settings.component.ts`

### New Services
- `src/app/shared/services/chat-session.service.ts`
- `src/app/shared/services/config.service.ts`
- `src/app/shared/services/plan.service.ts`

### Backend
- No changes required (all storage in localStorage for now)
- Future: Add `/api/config/*` endpoints when backend persistence needed

---

## Verification

1. **Branding**: Verify "AICDP" appears in login page and sidebar
2. **Settings**: Navigate to `/settings/ontology` and `/settings/labels`, verify config loads
3. **Chat History**: Start multiple chat sessions, refresh page, verify history persists in sidebar
4. **Flow A - Save to Plan**: Start new chat → get AI response → click "Save to Plan" → verify new plan created
5. **Flow B - Agent Plan**: Chat with AI → verify execution plan is returned and linked
6. **Flow C - Run Plan**: Use plan selector dropdown → pick existing plan → verify chat context is scoped to plan

---

## UI Layouts

### 1. Workspace (Main Chat Area)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [AICDP Logo]   Workspace   Plans   ⚙️ Settings                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────┐  ┌─────────────────────────────────────────────┐ │
│  │  CHAT HISTORY    │  │  ┌─────────────────────────────────────┐   │ │
│  │                  │  │  │  📋 Select Plan ▼  │  + New Chat    │   │ │
│  │  + New Chat      │  │  └─────────────────────────────────────┘   │ │
│  │                  │  │                                             │ │
│  │  ─── Today ───   │  │  ┌─────────────────────────────────────┐   │ │
│  │  💬 Query users  │  │  │ 🤖 AI                                │   │ │
│  │  💬 Cart abandn  │  │  │ I'll analyze the database schema... │   │ │
│  │                  │  │  │                                      │   │ │
│  │  ─ Yesterday ─   │  │  │ 📊 EXECUTION PLAN                   │   │ │
│  │  💬 Sales report │  │  │ Goal: Find abandoned cart users      │   │ │
│  │  💬 User segm... │  │  │ Tables: users, carts                 │   │ │
│  │                  │  │  │ Filters: inactive > 24h              │   │ │
│  │  ─ This Week ─   │  │  │                                      │   │ │
│  │  💬 Product an.. │  │  │ ✅ RESULT                            │   │ │
│  │                  │  │  │ SELECT * FROM users WHERE...         │   │ │
│  │                  │  │  │                                      │   │ │
│  │                  │  │  │ [💾 Save to Plan] [📋 Copy SQL]      │   │ │
│  │                  │  │  └─────────────────────────────────────┘   │ │
│  │                  │  │                                             │ │
│  │  ────────────────│  │  👤 You                                     │ │
│  │  🔗 = Linked to  │  │  Find users with abandoned carts            │ │
│  │     a Plan       │  │                                             │ │
│  │                  │  ├─────────────────────────────────────────────┤ │
│  │                  │  │  [Type your message...              ] [➤]  │ │
│  └──────────────────┘  └─────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2. Save to Plan Dialog

```
┌───────────────────────────────────────────────────┐
│  💾 Save to Plan                              ✕  │
├───────────────────────────────────────────────────┤
│                                                   │
│  ○ Create New Plan                                │
│     ┌─────────────────────────────────────────┐  │
│     │ Plan Name: Abandoned Cart Analysis      │  │
│     └─────────────────────────────────────────┘  │
│     ┌─────────────────────────────────────────┐  │
│     │ Goal: Find users with items in cart     │  │
│     │ but haven't purchased in 24+ hours      │  │
│     └─────────────────────────────────────────┘  │
│                                                   │
│  ● Link to Existing Plan                          │
│     ┌─────────────────────────────────────────┐  │
│     │ ▼ VIP Customer Analysis              ▾  │  │
│     └─────────────────────────────────────────┘  │
│                                                   │
│                      [Cancel]  [💾 Save]         │
└───────────────────────────────────────────────────┘
```

### 3. Plan Selector Dropdown (in Workspace Header)

```
┌──────────────────────────────────────┐
│  📋 Select Plan ▼                    │
├──────────────────────────────────────┤
│  ○ No Plan (Free Chat)               │
│  ───────────────────────────────     │
│  ● VIP Customer Analysis             │
│  ○ Cart Abandonment Study            │
│  ○ Monthly Sales Report              │
│  ───────────────────────────────     │
│  + Create New Plan...                │
└──────────────────────────────────────┘
```

### 4. Plan Editor (with Linked Chats)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [AICDP Logo]   Workspace   Plans   ⚙️ Settings                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ← Back to Plans                              [Preview] [💾 Save]       │
│                                                                         │
│  ┌────────────────────────────────────────────┐  ┌──────────────────┐  │
│  │  PLAN DETAILS                              │  │ LINKED CHATS 💬  │  │
│  │                                            │  │                  │  │
│  │  Plan Name                                 │  │ 💬 Initial query │  │
│  │  ┌────────────────────────────────────┐   │  │    Jan 12, 2:30pm│  │
│  │  │ VIP Customer Analysis              │   │  │                  │  │
│  │  └────────────────────────────────────┘   │  │ 💬 Follow-up     │  │
│  │                                            │  │    Jan 13, 9:15am│  │
│  │  Goal                                      │  │                  │  │
│  │  ┌────────────────────────────────────┐   │  │ 💬 Refinement    │  │
│  │  │ Identify high-value customers with │   │  │    Jan 14, 11:00a│  │
│  │  │ 5+ purchases for targeted campaign │   │  │                  │  │
│  │  └────────────────────────────────────┘   │  │──────────────────│  │
│  │                                            │  │                  │  │
│  │  Current Situation                         │  │ [+ Start Chat]   │  │
│  │  ┌────────────────────────────────────┐   │  │                  │  │
│  │  │ Need to segment VIP users for Q1   │   │  │                  │  │
│  │  │ marketing initiative               │   │  │                  │  │
│  │  └────────────────────────────────────┘   │  │                  │  │
│  │                                            │  │                  │  │
│  │  MODULES                    [+ Add Module] │  │                  │  │
│  │  ┌────┐ → ┌────┐ → ┌────┐                 │  │                  │  │
│  │  │ A  │   │ S  │   │ E  │                 │  │                  │  │
│  │  └────┘   └────┘   └────┘                 │  │                  │  │
│  │                                            │  │                  │  │
│  └────────────────────────────────────────────┘  └──────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5. Settings Page

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [AICDP Logo]   Workspace   Plans   ⚙️ Settings                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────┐  ┌───────────────────────────────────────────┐  │
│  │  SETTINGS         │  │                                           │  │
│  │                   │  │  ONTOLOGY CONFIGURATION                   │  │
│  │  🗂️ Ontology  ●   │  │                                           │  │
│  │                   │  │  [Visual] [JSON]     [Import] [💾 Save]   │  │
│  │  🏷️ Label Rules   │  │                                           │  │
│  │                   │  │  ┌───────────────────────────────────────┐│  │
│  │                   │  │  │ ENTITIES                              ││  │
│  │                   │  │  │                                       ││  │
│  │                   │  │  │  📦 Customer     → Table: customers   ││  │
│  │                   │  │  │     └─ id, name, email, created_at    ││  │
│  │                   │  │  │                                       ││  │
│  │                   │  │  │  📦 Order        → Table: orders      ││  │
│  │                   │  │  │     └─ id, customer_id, total, date   ││  │
│  │                   │  │  │                                       ││  │
│  │                   │  │  │  📦 Product      → Table: products    ││  │
│  │                   │  │  │     └─ id, name, price, category      ││  │
│  │                   │  │  │                                       ││  │
│  │                   │  │  │ [+ Add Entity]                        ││  │
│  │                   │  │  └───────────────────────────────────────┘│  │
│  │                   │  │                                           │  │
│  │                   │  │  RELATIONSHIPS                            │  │
│  │                   │  │  Customer ──1:N──> Order                  │  │
│  │                   │  │  Order ──N:1──> Product                   │  │
│  │                   │  │                                           │  │
│  └───────────────────┘  └───────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6. Label Rules Settings

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [AICDP Logo]   Workspace   Plans   ⚙️ Settings                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────┐  ┌───────────────────────────────────────────┐  │
│  │  SETTINGS         │  │                                           │  │
│  │                   │  │  LABEL RULES                              │  │
│  │  🗂️ Ontology      │  │                                           │  │
│  │                   │  │  [Import] [💾 Save]          [+ Add Label]│  │
│  │  🏷️ Label Rules ● │  │                                           │  │
│  │                   │  │  ┌───────────────────────────────────────┐│  │
│  │                   │  │  │ 🏷️ VIP Customer                       ││  │
│  │                   │  │  │ Users with 5+ purchases               ││  │
│  │                   │  │  │                                       ││  │
│  │                   │  │  │ Conditions:                           ││  │
│  │                   │  │  │ • orders.count >= 5                   ││  │
│  │                   │  │  │                                       ││  │
│  │                   │  │  │                         [Edit] [🗑️]   ││  │
│  │                   │  │  └───────────────────────────────────────┘│  │
│  │                   │  │                                           │  │
│  │                   │  │  ┌───────────────────────────────────────┐│  │
│  │                   │  │  │ 🏷️ Abandoned Cart                     ││  │
│  │                   │  │  │ Cart items > 0, inactive 24h+         ││  │
│  │                   │  │  │                                       ││  │
│  │                   │  │  │ Conditions:                           ││  │
│  │                   │  │  │ • cart.items > 0                      ││  │
│  │                   │  │  │ • user.last_active < now() - 24h      ││  │
│  │                   │  │  │                                       ││  │
│  │                   │  │  │                         [Edit] [🗑️]   ││  │
│  │                   │  │  └───────────────────────────────────────┘│  │
│  │                   │  │                                           │  │
│  └───────────────────┘  └───────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Design Decisions (Confirmed)
- **All storage**: localStorage for now (chat, plans, ontology, labels)
- **Navigation naming**: "Workspace" for the main chat area
- **Access control**: No restrictions - any user can edit Ontology/Labels
- **Backend**: No new API endpoints required initially
