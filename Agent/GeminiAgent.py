import Utils.secrets
from typing import Union
from Agent.Agent import Agent, LLMResponse
import google.generativeai as genai
import instructor
from langfuse import Langfuse

# Initialize Langfuse client
langfuse = Langfuse()

genai.configure(
    transport="grpc_asyncio"  # Ensure async gRPC transport
)

class GeminiAgent(Agent):

    def __init__(self, model: str):
        super().__init__(api_key=None, helicone_api_key=None)  # Helicone not needed for Gemini

        # Initialize Gemini client using the instructor library for structured outputs
        self._client = instructor.from_gemini(
            client=genai.GenerativeModel(model_name=model),
            use_async=True
        )
        self.model = model

    async def __call__(self, system_prompt: str, user_messages: list[dict], response_format: type[LLMResponse], helicone_headers: dict = None) -> Union[type[LLMResponse], None]:
        trace = langfuse.trace(name="GeminiAgent Call", metadata={"model": self.model})  # Start trace manually
        try:
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(user_messages)

            trace.event(name="prompt", metadata={"system_prompt": system_prompt, "messages": user_messages})

            # Create a span manually (No 'with' statement)
            span = trace.span(name="GeminiLLMResponse")

            # Start the span
            span.start()

            # ✅ Ensure this call is awaited (async required for gRPC)
            response = await self._client.chat.completions.create(
                messages=messages,
                response_model=response_format,
            )

            # End the span correctly
            span.end(status="success", output=response.dict() if response else None)

            # End trace correctly
            trace.end(status="success")

            return response  # Directly returning the structured response

        except Exception as e:
            span.end(status="error", error=str(e))  # Ensure span ends even on failure
            trace.end(status="error", error=str(e))  # Ensure trace ends correctly
            print(f"[ERROR] Error processing prompt: {e}")
            return None

# Instantiate agents
gemini_agent = GeminiAgent(model="gemini-2.0-flash-001")
gemini_pro_agent = GeminiAgent(model="models/gemini-1.5-pro-latest")
