class ChatService:

    def __init__(
        self,
        llmOrchestrator,
        session_service
    ):

        self.llm = llmOrchestrator
        self.sessions = session_service

    async def handle_message(
        self,
        session_id: str,
        user_message: str
    ):

        session = await self.sessions.load(
            session_id
        )

        session.messages.append({
            "role": "user",
            "content": user_message
        })

        response = await self.llm.generate(
            session
        )

        await self.sessions.save(session)

        return response