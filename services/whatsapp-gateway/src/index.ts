import Fastify from "fastify";
import sensible from "@fastify/sensible";
import { config } from "./config.js";
import { registerRoutes } from "./routes.js";
import { WhatsAppGateway } from "./whatsapp.js";

const app = Fastify({
  logger: {
    level: config.LOG_LEVEL,
    transport:
      config.APP_ENV === "development"
        ? {
            target: "pino-pretty"
          }
        : undefined
  }
});

await app.register(sensible);

const gateway = new WhatsAppGateway(app.log);
await gateway.connect();
await registerRoutes(app, gateway);

app.listen({ host: config.WHATSAPP_HOST, port: config.WHATSAPP_PORT }).catch((error) => {
  app.log.error(error, "Failed to start WhatsApp gateway");
  process.exit(1);
});

