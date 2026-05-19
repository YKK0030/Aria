import dotenv from "dotenv";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";

const currentFile = fileURLToPath(import.meta.url);
const currentDir = path.dirname(currentFile);
const repoRoot = path.resolve(currentDir, "../../../");
dotenv.config({ path: path.join(repoRoot, ".env") });

const envSchema = z.object({
  APP_ENV: z.string().default("development"),
  LOG_LEVEL: z.string().default("info"),
  WHATSAPP_PORT: z.coerce.number().default(3001),
  WHATSAPP_HOST: z.string().default("0.0.0.0"),
  WHATSAPP_SESSION_DIR: z.string().default(".data/whatsapp-auth"),
  WHATSAPP_WEBHOOK_URL: z.string().url(),
  WHATSAPP_API_KEY: z.string().min(1),
  WHATSAPP_WEBHOOK_API_KEY: z.string().default(""),
  WHATSAPP_AUTO_READ: z
    .string()
    .default("true")
    .transform((value) => value.toLowerCase() === "true"),
  WHATSAPP_ALLOWED_NUMBERS: z.string().default(""),
  WHATSAPP_ALLOWED_GROUP_IDS: z.string().default(""),
  WHATSAPP_ALLOWED_GROUP_NAMES: z.string().default(""),
  WHATSAPP_PAIRING_NUMBER: z.string().default("")
});

const splitCsv = (value: string) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

const env = envSchema.parse(process.env);

export const config = {
  ...env,
  allowedNumbers: splitCsv(env.WHATSAPP_ALLOWED_NUMBERS),
  allowedGroupIds: splitCsv(env.WHATSAPP_ALLOWED_GROUP_IDS),
  allowedGroupNames: splitCsv(env.WHATSAPP_ALLOWED_GROUP_NAMES),
  webhookApiKey: env.WHATSAPP_WEBHOOK_API_KEY || env.WHATSAPP_API_KEY,
  repoRoot
};
