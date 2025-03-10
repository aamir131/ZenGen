import sys
import asyncio
import json

from pydantic import BaseModel

from Agent.OpenAIAgent import gpt_4o_openai_agent

def _load_file(file_path: str) -> str:
  with open(file_path, 'r', encoding='utf-8') as file:
    return file.read()
    
def write_to_file(output_file: str, generated_data: str):
  with open(output_file, 'w', encoding='utf-8') as file:
    file.write(generated_data)

def write_convo_to_file(output_file: str, data: list[dict]):
  with open(output_file, 'w', encoding='utf-8') as file:
    json.dump(data, file, indent=4)
  
def load_convo_from_file(file_path: str) -> list[dict]:
  with open(file_path, 'r', encoding='utf-8') as file:
    return json.load(file)
  
class Answer(BaseModel):
  explanation: str
  analysis: str

async def generate_content_based_on_prompt(
  customer_prompt_chain: list[dict],
  customer_prompt: str,
  project_description: str, table: str, call_transcript: str, 
  topic: str, textbox_user_prompt: str, length: str) -> tuple[Answer, list[dict]]:
  
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
          [customer_prompt, project_description_data, table_data, call_transcripts_data, topic_data, textbox_user_prompt_data, document_length]
  )

  prompt_chain = customer_prompt_chain + [{"role": "user", "content": collated_data}]
  generated_data = await gpt_4o_openai_agent(system_prompt, prompt_chain, Answer ,{})
  updated_prompt_chain = [*prompt_chain, {"role": "assistant", "content": generated_data}]
  if generated_data:
    return generated_data, updated_prompt_chain
  else:
    raise Exception("No data generated")

if __name__ == "__main__":
  customer_prompt_chain: list[dict] = load_convo_from_file(sys.argv[1])
  customer_prompt = sys.argv[2] #Customer Prompt: The customer is asking: Generate an initial analysis based on the following information, and requirements:
  project_description = sys.argv[3]
  table_path = sys.argv[4]
  call_transcript_path = sys.argv[5]
  topic = sys.argv[6]
  textbox_user_prompt = sys.argv[7]
  length = sys.argv[8]

  table = _load_file(table_path)
  call_transcript = _load_file(call_transcript_path)

  output_analysis_file = sys.argv[9]
  output_other_data_file = sys.argv[10]
  output_convo_file = sys.argv[11]
  

  generated_data, updated_prompt_chain = asyncio.run(generate_content_based_on_prompt(
    customer_prompt_chain, customer_prompt, project_description, table, call_transcript, topic, textbox_user_prompt, length
  ))

  write_to_file(output_analysis_file, generated_data.analysis)
  write_to_file(output_other_data_file, generated_data.explanation)
  write_convo_to_file(output_convo_file, updated_prompt_chain)