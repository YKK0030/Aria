import { FastifyInstance } from "fastify";
import { z } from "zod";
import { config } from "./config.js";
import { normalizeNumberToJid } from "./allowlist.js";
import { WhatsAppGateway } from "./whatsapp.js";

const sendSchema = z.object({
  to: z.string().min(1),
  text: z.string().min(1)
});

const readSchema = z.object({
  chatId: z.string().min(1),
  messageId: z.string().min(1),
  participant: z.string().optional()
});

export const registerRoutes = async (app: FastifyInstance, gateway: WhatsAppGateway) => {
  app.get("/health", async () => ({
    ok: true,
    service: "whatsapp-gateway",
    status: gateway.getStatus()
  }));

  app.get("/session/status", async () => ({
    ok: true,
    service: "whatsapp-gateway",
    status: gateway.getStatus()
  }));

  app.get("/allowlist", async () => ({
    numbers: config.allowedNumbers.map(normalizeNumberToJid),
    groups: config.allowedGroupIds,
    groupNames: config.allowedGroupNames
  }));

  app.post("/messages/send", async (request, reply) => {
    const apiKey = request.headers["x-api-key"];

    if (apiKey !== config.WHATSAPP_API_KEY) {
      return reply.unauthorized("Invalid API key");
    }

    const payload = sendSchema.parse(request.body);
    const result = await gateway.sendMessage(payload.to, payload.text);
    return reply.send({ ok: true, result });
  });

  app.post("/messages/read", async (request, reply) => {
    const apiKey = request.headers["x-api-key"];

    if (apiKey !== config.WHATSAPP_API_KEY) {
      return reply.unauthorized("Invalid API key");
    }

    const payload = readSchema.parse(request.body);
    await gateway.markRead(payload);
    return reply.send({ ok: true });
  });
};
