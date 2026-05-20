import { sendChatMessage, streamChatMessage } from "../../../api/backendClient";

export function sendMessage(sessionId, message) {
  return sendChatMessage(sessionId, message);
}

export function streamMessage(sessionId, message, onEvent) {
  return streamChatMessage(sessionId, message, onEvent);
}
