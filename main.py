import sys
import asyncio

from Agent.OpenAIAgent import gpt_4o_openai_agent

def _load_file(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()
    
def write_to_file(output_file: str, generated_data: str):
        with open(output_file, 'w', encoding='utf-8') as file:
                file.write(generated_data)

async def generate_content_based_on_prompt(
project_description: str, table: str, call_transcript: str, 
            topic: str, textbox_user_prompt: str, length: str) -> str:
        
        tables = [table]
        call_transcripts = [call_transcript]

        system_prompt = _load_file("./PromptEngine/SystemPrompts/basic_generation.txt")
        project_description_data = "The project description is: " + project_description
        table_data = "Our tables are: " + "\n".join(tables)
        call_transcripts_data = "\n".join(call_transcripts)
        topic_data = "Topic is: " + "\n" + topic
        textbox_user_prompt_data = "textbox_user_prompt: " + "\n" + textbox_user_prompt
        document_length = "The length of the analysis is: " + length

        collated_data = "\n".join(
               [project_description_data, table_data, call_transcripts_data, topic_data, textbox_user_prompt_data, document_length]
        )

        user_prompt = [{"role": "user", "content": collated_data}]
        generated_data = await gpt_4o_openai_agent.run(system_prompt, user_prompt, {})
        if generated_data:
                return generated_data
        else:
               raise Exception("No data generated")

if __name__ == "__main__":
        project_description = sys.argv[1]
        table_path = sys.argv[2]
        call_transcript_path = sys.argv[3]
        topic = sys.argv[4]
        textbox_user_prompt = sys.argv[5]
        length = sys.argv[6]

        table = _load_file(table_path)
        call_transcript = _load_file(call_transcript_path)

        output_file = sys.argv[7]

        generated_data = asyncio.run(generate_content_based_on_prompt(project_description, table, call_transcript, topic, textbox_user_prompt, length))
        write_to_file(output_file, generated_data)