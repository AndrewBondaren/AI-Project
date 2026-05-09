import { compileRequest } from "../../../api/backendClient";

export function compile(code) {
  return compileRequest(code);
}