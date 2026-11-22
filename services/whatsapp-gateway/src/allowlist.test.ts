import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { isChatAllowed } from "./allowlist.js";

test("managed policy allows only listed WhatsApp chat IDs and honors blocks", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "aria-allowlist-"));
  const policyPath = path.join(root, "policy.json");
  try {
    await writeFile(policyPath, JSON.stringify({
      whatsapp: {
        enabled: true,
        allowlist_managed: true,
        allowed_chat_ids: ["123@s.whatsapp.net", "group@g.us"],
        blocked_chat_ids: ["blocked@g.us"],
      },
    }));
    assert.equal(isChatAllowed("123@s.whatsapp.net", undefined, policyPath), true);
    assert.equal(isChatAllowed("group@g.us", undefined, policyPath), true);
    assert.equal(isChatAllowed("blocked@g.us", undefined, policyPath), false);
    assert.equal(isChatAllowed("other@s.whatsapp.net", undefined, policyPath), false);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("an empty managed allowlist blocks every chat", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "aria-allowlist-"));
  const policyPath = path.join(root, "policy.json");
  try {
    await writeFile(policyPath, JSON.stringify({
      whatsapp: { allowlist_managed: true, allowed_chat_ids: [], blocked_chat_ids: [] },
    }));
    assert.equal(isChatAllowed("123@s.whatsapp.net", undefined, policyPath), false);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("invalid policy falls back to the configured startup allowlist", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "aria-allowlist-"));
  const policyPath = path.join(root, "policy.json");
  try {
    await writeFile(policyPath, "not-json");
    assert.equal(isChatAllowed("unlisted@g.us", undefined, policyPath), false);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
