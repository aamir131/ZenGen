import json
def load_file(file_path: str) -> str:
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