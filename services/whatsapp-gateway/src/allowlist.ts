import { config } from "./config.js";

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

export const isChatAllowed = (chatId: string, groupName?: string) => {
  if (chatId.endsWith("@g.us")) {
    return isAllowedGroupChat(chatId, groupName);
  }

  return isAllowedUserChat(chatId);
};

