import { sendChatMessage, streamChatMessage, cancelStream } from "../../../api/backendClient";

export function sendMessage(sessionId, message) {
  return sendChatMessage(sessionId, message);
}

export function streamMessage(sessionId, message, onEvent, options = {}) {
  return streamChatMessage(sessionId, message, onEvent, options);
}

export { cancelStream };
