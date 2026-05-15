import { readFileSync } from "node:fs";
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

import viteConfig from "../vite.config.js";

test("ARGUS MVP app exposes upload gate, brief mode, and semantic search mode", () => {
  const appSource = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
  const cssSource = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");

  assert.match(appSource, /Загрузить каталог/);
  assert.match(appSource, /className="auth-title">ARGUS/);
  assert.match(appSource, /Зарегистрироваться/);
  assert.match(appSource, /Выйти/);
  assert.match(appSource, /restoreSession/);
  assert.match(appSource, /signIn/);
  assert.match(appSource, /signUp/);
  assert.match(appSource, /logoutAuth/);
  assert.doesNotMatch(appSource, /minLength=/);
  assert.match(appSource, /Authorization/);
  assert.match(appSource, /Bearer \$\{accessToken\}/);
  assert.match(appSource, /готовые embeddings/);
  assert.match(appSource, /<span className="mode-tab-label">Планирование<\/span>/);
  assert.doesNotMatch(appSource, /Планирование брифа/);
  assert.match(appSource, /<span className="mode-tab-label">Поиск<\/span>/);
  assert.doesNotMatch(appSource, /Семантический поиск/);
  assert.match(appSource, /Гайд по промптам/);
  assert.match(appSource, /PROMPT_GUIDE_ITEMS/);
  assert.match(appSource, /<div className="m-footer">argus<\/div>/);
  assert.doesNotMatch(appSource, /ARGUS MVP · PostgreSQL\/pgvector · LM Studio · локальная демонстрация/);
  assert.match(appSource, /className="orb-canvas"/);
  assert.match(appSource, /function ArgusOrb\(\{ loading = false, particles = true, compact = false \}\)/);
  assert.match(appSource, /const particleCount = particles \? 300 : 0;/);
  assert.match(appSource, /const showNebula = particles \|\| active;/);
  assert.match(appSource, /if \(showNebula\) \{/);
  assert.match(appSource, /<ArgusOrb loading=\{false\} particles=\{false\} compact \/>/);
  assert.match(appSource, /function Sidebar\(\{ catalogReady, userEmail, view, onViewChange, onReset, onLogout \}\)/);
  assert.doesNotMatch(appSource, /className="brand-name"/);
  assert.doesNotMatch(appSource, /<span className="brand-name">ARGUS<\/span>/);
  assert.match(appSource, /id="sidebar-collapse-toggle"/);
  assert.match(appSource, /className="sidebar-toggle-input"/);
  assert.match(appSource, /htmlFor="sidebar-collapse-toggle"/);
  assert.match(appSource, /className="icon-btn sidebar-toggle"/);
  assert.match(appSource, /catalog: \[/);
  assert.match(appSource, /<Icon d=\{P\.catalog\} size=\{16\}/);
  assert.match(appSource, /<Icon d=\{P\.files\} size=\{16\}/);
  assert.doesNotMatch(appSource, /<Icon d=\{P\.plug\} size=\{15\}/);
  assert.doesNotMatch(appSource, /<Icon d=\{P\.clock\} size=\{15\}/);
  assert.match(appSource, /function CatalogStatus\(\{ status \}\)/);
  assert.match(appSource, /<CatalogStatus status=\{status\} \/>/);
  assert.match(appSource, /ИЗБРАННОЕ/);
  assert.match(appSource, /НЕДАВНИЕ ЗАПРОСЫ/);
  assert.doesNotMatch(appSource, /group\.items/);
  assert.doesNotMatch(appSource, /recent-group/);
  assert.doesNotMatch(appSource, /СЕГОДНЯ/);
  assert.doesNotMatch(appSource, /ВЧЕРА/);
  assert.doesNotMatch(appSource, /7 ДНЕЙ/);
  assert.doesNotMatch(appSource, /item\.shortcut/);
  assert.doesNotMatch(appSource, /shortcut-icon/);
  assert.doesNotMatch(appSource, /shortcut-key/);
  assert.match(appSource, /Документы/);
  assert.doesNotMatch(appSource, /function Sidebar\(\{ status,/);
  assert.doesNotMatch(appSource, />Экспорт</);
  assert.doesNotMatch(appSource, />MVP</);
  assert.match(appSource, /\/api\/catalog\/upload/);
  assert.match(appSource, /\/api\/chat/);
  assert.match(appSource, /\/api\/search/);
  assert.match(appSource, /limit: 3/);
  assert.match(appSource, /content: body\.message/);
  assert.doesNotMatch(appSource, /score \$\{score\}/);
  assert.match(appSource, /modeLocked/);
  assert.match(appSource, /disabled=\{modeLocked \|\| loading\}/);
  assert.match(appSource, /setMode\("brief"\)/);
  assert.match(cssSource, /--surface-sidebar/);
  assert.match(cssSource, /font-family: sans-serif;/);
  assert.doesNotMatch(cssSource, /Plus Jakarta Sans/);
  assert.match(cssSource, /\.auth-shell/);
  assert.match(cssSource, /\.auth-card/);
  assert.match(cssSource, /\.main \{[^}]*background: rgba\(15,24,40,\s*\.72\)/s);
  assert.match(cssSource, /\.sidebar \{[^}]*background: rgba\(5,13,24,\s*\.76\)/s);
  assert.match(cssSource, /\.s-head \{[^}]*justify-content: center/s);
  assert.doesNotMatch(cssSource, /\.brand-name/);
  assert.match(cssSource, /\.sidebar-toggle-input/);
  assert.match(cssSource, /\.app:has\(\.sidebar-toggle-input:checked\) \{[^}]*grid-template-columns: 76px 1fr/s);
  assert.match(cssSource, /\.app:has\(\.sidebar-toggle-input:checked\) \.sidebar-toggle-input \{ top: 48px; left: 56px;/);
  assert.match(cssSource, /\.app:has\(\.sidebar-toggle-input:checked\) \.sidebar-toggle \{\s*position: absolute; top: 48px; left: 56px; width: 28px; height: 28px;/);
  assert.doesNotMatch(cssSource, /\.app:has\(\.sidebar-toggle-input:checked\) \.sidebar-toggle \{\s*position: absolute; top: 62px; left: 22px;/);
  assert.match(cssSource, /\.app:has\(\.sidebar-toggle-input:checked\) \.nav-label/s);
  assert.match(cssSource, /\.app:has\(\.sidebar-toggle-input:checked\) \.s-scroll/s);
  assert.match(cssSource, /\.s-nav \{[^}]*gap: 4px/s);
  assert.match(cssSource, /\.nav-link \{[^}]*height: 42px/s);
  assert.match(cssSource, /\.nav-link \{[^}]*padding: 0 14px/s);
  assert.match(cssSource, /\.nav-link \{[^}]*font-size: 15px/s);
  assert.match(cssSource, /\.orb-wrap-compact/);
  assert.match(cssSource, /\.greeting-name \{[^}]*font-size: 30px/s);
  assert.match(cssSource, /\.greeting-q \{[^}]*font-size: 21px/s);
  assert.match(cssSource, /\.s-shortcuts/);
  assert.match(cssSource, /\.s-shortcut \{[^}]*min-height: 32px/s);
  assert.match(cssSource, /\.s-shortcut \{[^}]*font-size: 14px/s);
  assert.doesNotMatch(cssSource, /\.recent-group/);
  assert.doesNotMatch(cssSource, /\.shortcut-icon/);
  assert.doesNotMatch(cssSource, /\.shortcut-key/);
  assert.match(cssSource, /\.catalog-status/);
  assert.match(cssSource, /\.logout-btn/);
  assert.match(cssSource, /\.mode-tab-active/);
  assert.match(cssSource, /\.mode-tab:disabled/);
});

test("Local auth client stores bearer sessions", () => {
  const clientSource = readFileSync(new URL("../src/authClient.js", import.meta.url), "utf8");

  assert.match(clientSource, /ARGUS_AUTH_SESSION/);
  assert.match(clientSource, /signIn/);
  assert.match(clientSource, /signUp/);
  assert.match(clientSource, /restoreSession/);
  assert.match(clientSource, /clearSession/);
  assert.doesNotMatch(clientSource, /supabase/i);
});

test("Vite reads shared environment variables from the project root", () => {
  const projectRoot = fileURLToPath(new URL("../..", import.meta.url));

  assert.equal(viteConfig.envDir, projectRoot);
});

test("Catalog supplier list loading guards stale requests and reconciles selection from refs", () => {
  const appSource = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");

  assert.match(appSource, /const listRequestRef = useRef\(0\);/);
  assert.match(appSource, /const selectedIdRef = useRef\(null\);/);
  assert.match(appSource, /if \(listRequestRef\.current !== requestId\) return;/);
  assert.match(appSource, /selectedIdRef\.current/);
});
