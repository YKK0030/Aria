import { config } from "./config.js";
import fs from "node:fs";
import path from "node:path";

const normalizeDigits = (value: string) => value.replace(/\D/g, "");

export const normalizeNumberToJid = (value: string) => {
  const digits = normalizeDigits(value);
  return digits ? `${digits}@s.whatsapp.net` : value;
};

export const isAllowedUserChat = (chatId: string) => {
  if (!config.allowedNumbers.length) {
    return false;
  }

  const allowedJids = new Set(config.allowedNumbers.map(normalizeNumberToJid));
  return allowedJids.has(chatId);
};

export const isAllowedGroupChat = (chatId: string, groupName?: string) => {
  if (config.allowedGroupIds.includes(chatId)) {
    return true;
  }

  if (groupName && config.allowedGroupNames.includes(groupName)) {
    return true;
  }

  return false;
};

type DynamicChannelPolicy = {
  enabled?: unknown;
  allowlist_managed?: unknown;
  allowed_chat_ids?: unknown;
  blocked_chat_ids?: unknown;
};

const dynamicPolicyPath = path.isAbsolute(config.ACCESS_POLICY_OVERRIDES_FILE)
  ? config.ACCESS_POLICY_OVERRIDES_FILE
  : path.resolve(config.repoRoot, config.ACCESS_POLICY_OVERRIDES_FILE);

export const isChatAllowed = (
  chatId: string,
  groupName?: string,
  policyPath: string = dynamicPolicyPath
) => {
  try {
    const document = JSON.parse(fs.readFileSync(policyPath, "utf8")) as Record<string, DynamicChannelPolicy>;
    const channel = document.whatsapp;
    if (channel?.enabled === false) return false;
    if (channel?.allowlist_managed === true) {
      const allowed = Array.isArray(channel.allowed_chat_ids) ? channel.allowed_chat_ids : [];
      const blocked = Array.isArray(channel.blocked_chat_ids) ? channel.blocked_chat_ids : [];
      return !blocked.includes(chatId) && allowed.includes(chatId);
    }
  } catch {
    // Fall back to the startup allowlist until a managed policy file is available.
  }

  if (chatId.endsWith("@g.us")) {
    return isAllowedGroupChat(chatId, groupName);
  }

  return isAllowedUserChat(chatId);
};

