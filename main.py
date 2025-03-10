import sys, asyncio

from Utils.file_utils import load_convo_from_file, write_to_file, write_convo_to_file, load_file

from PromptEngine.PromptEngine import engine

if __name__ == "__main__":
  customer_prompt_chain: list[dict] = load_convo_from_file(sys.argv[1])
  customer_prompt = sys.argv[2]
  project_description_path = sys.argv[3]
  table_path = sys.argv[4]
  call_transcript_path = sys.argv[5]
  topic = sys.argv[6]
  textbox_user_prompt = sys.argv[7]
  length = sys.argv[8]

  project_description = load_file(project_description_path)
  table = load_file(table_path)
  call_transcript = load_file(call_transcript_path)

  output_analysis_file = sys.argv[9]
  output_explanation_file = sys.argv[10]
  output_convo_file = sys.argv[11]
  
  generated_data, updated_prompt_chain = asyncio.run(engine.generate_content(
    customer_prompt_chain, customer_prompt, project_description, table, call_transcript, topic, textbox_user_prompt, length
  ))

  write_to_file(output_analysis_file, generated_data.analysis)
  write_to_file(output_explanation_file, generated_data.explanation)
  write_convo_to_file(output_convo_file, updated_prompt_chain)

  
  #python main.py ./test_data/customer_prompt_chain.json "What's the customer's main complaint?" "Analyzing customer complaints for telecom support" ./test_data/test_table.txt ./test_data/management_call.txt "test_topic" "test_textbox" "short" "analysis_output.txt" "explanation_file.txt" "promp_chain.json"