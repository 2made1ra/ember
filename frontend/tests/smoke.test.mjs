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
  assert.match(appSource, /minLength=\{mode === "signup" \? 6 : undefined\}/);
  assert.match(appSource, /Authorization/);
  assert.match(appSource, /Bearer \$\{accessToken\}/);
  assert.match(appSource, /готовые embeddings/);
  assert.match(appSource, /Планирование брифа/);
  assert.match(appSource, /Семантический поиск/);
  assert.match(appSource, /Гайд по промптам/);
  assert.match(appSource, /PROMPT_GUIDE_ITEMS/);
  assert.match(appSource, /className="orb-canvas"/);
  assert.match(appSource, /СОСТОЯНИЕ/);
  assert.match(appSource, /Документы/);
  assert.doesNotMatch(appSource, /PINNED_CHATS/);
  assert.doesNotMatch(appSource, /CHAT_HISTORY/);
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
  assert.match(cssSource, /\.auth-shell/);
  assert.match(cssSource, /\.auth-card/);
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
