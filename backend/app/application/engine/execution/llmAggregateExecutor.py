import asyncio
import json

from app.application.engine.nodes.pojo.llmNode import LLMNode


class LLMAggregateExecutor:
    """
    Выполняет одну LLM temperature-группу как единый агрегированный вызов.

    Порядок:
      1. PromptAggregator собирает запрос из всех нод группы
      2. Один client.chat() с агрегированным JSON
      3. Ответ разбивается по node_id — каждая секция валидируется
         через contract_json ноды
      4. При WARN — repair loop внутри conversation (до session.repair_iterations)
      5. Результаты пишутся в state.node_results[node_id]
    """

    def __init__(self, payload_builder, router):
        self.payload_builder = payload_builder
        self.router = router

    async def execute(self, llm_group, plan, state, context):

        # собираем CompiledNode для нод группы (плоский список из всех уровней)
        node_ids = [nid for level in llm_group.levels for nid in level]
        nodes = [plan.nodes[nid].node for nid in node_ids]

        client = self.router.get(state.session.llm_provider)

        # строим агрегированный запрос
        payload = self.prompt_aggregator.build(nodes=nodes, state=state)

        messages = [
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
        ]

        max_attempts = state.session.repair_iterations
        attempt = 0

        while attempt <= max_attempts:

            raw = await client.chat(
                model=state.session.model,
                messages=messages,
            )

            # парсим JSON-ответ
            try:
                response = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError as e:
                messages.append(self._repair_msg(
                    error=f"JSON parse error: {e}",
                    raw=raw,
                    hint="Return a single valid JSON object with keys matching node ids",
                ))
                attempt += 1
                continue

            # валидируем каждую секцию через contract_json ноды
            failed_sections, node_errors = self._validate_sections(nodes, response)

            if not failed_sections:
                # всё ок — пишем результаты в state
                for node in nodes:
                    state.node_results[node.id] = response[node.id]
                    state.node_status[node.id] = "success"
                return

            # есть ошибки — repair loop
            messages.append({"role": "assistant", "content": raw})
            messages.append(self._repair_msg(
                error=json.dumps(node_errors, ensure_ascii=False),
                raw=raw,
                hint="Fix only the failed sections. Return the full JSON with all node ids.",
            ))
            attempt += 1

        # исчерпали попытки — фиксируем ошибки для нод у которых нет результата
        for node in nodes:
            if node.id not in state.node_results:
                state.node_status[node.id] = "failed"
                state.node_errors.setdefault(node.id, []).append({
                    "error": "repair_limit_exceeded",
                })

    # --------------------------------------------------

    def _validate_sections(
        self,
        nodes: list,
        response: dict,
    ) -> tuple[list[str], dict]:
        """
        Валидирует каждую секцию ответа через contract_json ноды.
        Возвращает (список id нод с ошибками, dict с описанием ошибок).
        """
        failed = []
        errors = {}

        for node in nodes:
            node_id = node.id

            if node_id not in response:
                failed.append(node_id)
                errors[node_id] = f"missing section '{node_id}' in response"
                continue

            if node.contract_json is None:
                # нет контракта — секция принимается as-is
                continue

            try:
                node.contract_json.model_validate(response[node_id])
            except Exception as e:
                failed.append(node_id)
                errors[node_id] = str(e)

        return failed, errors

    def _repair_msg(self, error: str, raw: str, hint: str) -> dict:
        return {
            "role": "user",
            "content": json.dumps({
                "type": "repair",
                "error": error,
                "hint": hint,
            }, ensure_ascii=False),
        }