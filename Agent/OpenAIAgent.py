from Agent.Agent import Agent, LLMResponse
from langfuse.openai import openai

from Utils.secrets import openai_api_key, helicone_api_key

class OpenAIAgent(Agent):

    def __init__(self, api_key: str, helicone_api_key: str, model: str):
        super().__init__(api_key, helicone_api_key)

        self._client = openai.AsyncOpenAI(api_key=openai_api_key, base_url="https://oai.helicone.ai/v1",
                    default_headers={
                        "Helicone-Auth": f"Bearer {helicone_api_key}",
                    }
                )
        self.model = model
    
    async def __call__(self, system_prompt: str, user_messages: list[dict], response_format: type[LLMResponse], helicone_headers: dict) -> LLMResponse | None:
        try:
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            messages.extend(user_messages)

            response = await self._client.beta.chat.completions.parse(
                model=self.model,
                messages=messages,
                response_format=response_format,
                extra_headers=helicone_headers,
            )
            return response.choices[0].message.parsed
        except Exception as e:
            print(f"[ERROR] Error processing prompt: {e}")
            return None
        
    async def run(self, system_prompt: str, user_messages: list[dict], helicone_headers: dict) -> str:
        try:
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            messages.extend(user_messages)

            response = await self._client.beta.chat.completions.parse(
                model=self.model,
                messages=messages,
                extra_headers=helicone_headers,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[ERROR] Error processing prompt: {e}")
            return None
    
gpt_4o_openai_agent = OpenAIAgent(openai_api_key, helicone_api_key, model="gpt-4o")
o3_mini_openai_agent = OpenAIAgent(openai_api_key, helicone_api_key, model="o3-mini")