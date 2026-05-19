export type ChannelKind = "whatsapp";

export interface ChatDescriptor {
  chatId: string;
  senderId: string;
  fromMe: boolean;
  pushName?: string;
  groupName?: string;
  isGroup: boolean;
}

export interface InboundMessageEvent extends ChatDescriptor {
  channel: ChannelKind;
  messageId: string;
  text: string;
  timestamp: number;
}

export interface SendMessageRequest {
  to: string;
  text: string;
}

export interface MarkReadRequest {
  chatId: string;
  messageId: string;
  participant?: string;
}

