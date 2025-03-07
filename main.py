from Agent.OpenAIAgent import gpt_4o_openai_agent

def _load_file(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

async def generate_content_based_on_prompt(
project_description: str, tables: list[str], call_transcripts: list[str], 
            subtitle: str, textbox_user_prompt: str, length: str) -> str:

        system_prompt = _load_file("./PromptEngine/SystemPrompt/basic_generation.txt")
        table_data = "Our tables are: " + "\n".join(tables)
        call_transcripts_data = "\n".join(call_transcripts)
        subtitle_data = "Subtitle is: " + "\n" + subtitle
        textbox_user_prompt_data = "textbox_user_prompt: " + "\n" + textbox_user_prompt

        collated_data = table_data + call_transcripts_data + subtitle_data + textbox_user_prompt_data

        user_prompt = [{"role": "user", "content": collated_data}]
        generated_data = await gpt_4o_openai_agent(system_prompt, user_prompt, None, {})
        if generated_data:
                return generated_data
        return "" # raise an error instead

def main(project_description: str, tables: list[str], call_transcripts: list[str], 
            subtitle: str, user_prompt: str, length: str):
            return generate_content_based_on_prompt(project_description, tables, call_transcripts, subtitle, user_prompt, length)