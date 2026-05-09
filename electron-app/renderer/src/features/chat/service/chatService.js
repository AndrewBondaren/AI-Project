import { sendChatMessage } from "../../../api/backendClient";

export function sendMessage(sessionId, message) {
  return sendChatMessage(sessionId, message);
}