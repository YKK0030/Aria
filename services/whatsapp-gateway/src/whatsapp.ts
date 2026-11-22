import makeWASocket, {
  DisconnectReason,
  WASocket,
  fetchLatestBaileysVersion,
  isJidGroup,
  useMultiFileAuthState
} from "baileys";
import axios from "axios";
import qrcode from "qrcode-terminal";
import { Boom } from "@hapi/boom";
import { config } from "./config.js";
import { isChatAllowed, normalizeNumberToJid } from "./allowlist.js";
import type { InboundMessageEvent, MarkReadRequest } from "./types.js";

type Logger = {
  info: (obj: unknown, msg?: string) => void;
  warn: (obj: unknown, msg?: string) => void;
  error: (obj: unknown, msg?: string) => void;
};

export class WhatsAppGateway {
  private socket?: WASocket;
  private readonly logger: Logger;
  private connectionState: "connecting" | "open" | "closed" = "connecting";

  constructor(logger: Logger) {
    this.logger = logger;
  }

  async connect() {
    this.connectionState = "connecting";
    const { state, saveCreds } = await useMultiFileAuthState(config.WHATSAPP_SESSION_DIR);
    const { version } = await fetchLatestBaileysVersion();

    this.socket = makeWASocket({
      auth: state,
      printQRInTerminal: false,
      version
    });

    this.socket.ev.on("creds.update", saveCreds);
    this.socket.ev.on("connection.update", async (update) => {
      if (update.qr) {
        qrcode.generate(update.qr, { small: true });
        this.logger.info({}, "Scan the QR above to authenticate WhatsApp");
      }

      if (update.connection === "open") {
        this.connectionState = "open";
        this.logger.info({}, "WhatsApp connection is open");

        if (config.WHATSAPP_PAIRING_NUMBER) {
          this.logger.warn({}, "Pairing number is configured but QR auth already opened");
        }
      }

      if (update.connection === "close") {
        this.connectionState = "closed";
        const boom = update.lastDisconnect?.error as Boom | undefined;
        const shouldReconnect = boom?.output?.statusCode !== DisconnectReason.loggedOut;

        this.logger.warn({ reason: boom?.output?.statusCode }, "WhatsApp connection closed");

        if (shouldReconnect) {
          await this.connect();
        }
      }
    });

    this.socket.ev.on("messages.upsert", async ({ messages, type }) => {
      if (type !== "notify") {
        return;
      }

      for (const message of messages) {
        try {
          const chatId = message.key.remoteJid;
          const messageId = message.key.id;

          if (!chatId || !messageId || message.key.fromMe) {
            continue;
          }

          const text =
            message.message?.conversation ??
            message.message?.extendedTextMessage?.text ??
            message.message?.imageMessage?.caption ??
            message.message?.videoMessage?.caption ??
            "";

          if (!text.trim()) {
            continue;
          }

          let groupName: string | undefined;
          if (isJidGroup(chatId)) {
            try {
              const metadata = await this.socket?.groupMetadata(chatId);
              groupName = metadata?.subject;
            } catch (error) {
              this.logger.warn({ error, chatId }, "Failed to load WhatsApp group metadata");
            }
          }

          if (!isChatAllowed(chatId, groupName)) {
            this.logger.info({ chatId, groupName }, "Ignoring message from non-allowlisted chat");
            continue;
          }

          const senderId = message.key.participant ?? chatId;
          const event: InboundMessageEvent = {
            channel: "whatsapp",
            chatId,
            senderId,
            fromMe: false,
            pushName: message.pushName ?? undefined,
            groupName,
            isGroup: Boolean(isJidGroup(chatId)),
            messageId,
            text,
            timestamp: Number(message.messageTimestamp ?? Date.now())
          };

          if (config.WHATSAPP_AUTO_READ) {
            try {
              await this.markRead({
                chatId,
                messageId,
                participant: message.key.participant ?? undefined
              });
            } catch (error) {
              this.logger.warn({ error, chatId, messageId }, "Failed to mark WhatsApp message as read");
            }
          }

          await this.forwardInboundEvent(event);
        } catch (error) {
          this.logger.error({ error }, "Failed to process inbound WhatsApp message");
        }
      }
    });

    const socketAuthState = this.socket as WASocket & {
      authState?: { creds?: { registered?: boolean } };
      requestPairingCode?: (phoneNumber: string) => Promise<string>;
    };

    if (
      config.WHATSAPP_PAIRING_NUMBER &&
      !socketAuthState.authState?.creds?.registered &&
      socketAuthState.requestPairingCode
    ) {
      const pairingCode = await socketAuthState.requestPairingCode(
        config.WHATSAPP_PAIRING_NUMBER.replace(/\D/g, "")
      );
      this.logger.info({ pairingCode }, "WhatsApp pairing code");
    }
  }

  getStatus() {
    const authState = this.socket as WASocket & {
      authState?: { creds?: { registered?: boolean } };
      user?: { id?: string; name?: string };
    };

    return {
      connected: this.connectionState === "open",
      connectionState: this.connectionState,
      registered: Boolean(authState.authState?.creds?.registered),
      userId: authState.user?.id ?? null,
      userName: authState.user?.name ?? null
    };
  }

  async sendMessage(to: string, text: string) {
    if (!this.socket) {
      throw new Error("WhatsApp socket is not connected");
    }

    const target = to.includes("@") ? to : normalizeNumberToJid(to);
    return this.socket.sendMessage(target, { text });
  }

  async markRead(request: MarkReadRequest) {
    if (!this.socket) {
      throw new Error("WhatsApp socket is not connected");
    }

    await this.socket.readMessages([
      {
        remoteJid: request.chatId,
        id: request.messageId,
        fromMe: false,
        participant: request.participant
      }
    ]);
  }

  private async forwardInboundEvent(event: InboundMessageEvent) {
    try {
      await axios.post(config.WHATSAPP_WEBHOOK_URL, event, {
        headers: {
          "Content-Type": "application/json",
          "x-api-key": config.webhookApiKey
        },
        timeout: 10_000
      });
    } catch (error) {
      this.logger.error({ error, chatId: event.chatId }, "Failed to forward WhatsApp event");
    }
  }
}
