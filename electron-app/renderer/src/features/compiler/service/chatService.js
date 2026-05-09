import { sendChatMessage } from "../../../api/backendClient";

export function sendMessage(message) {
  return sendChatMessage("default-session", message);
}