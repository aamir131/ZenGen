import os

from pathlib import Path

from dotenv import load_dotenv
from PromptEngine.structured_output_types import Answer
from langfuse.decorators import observe, langfuse_context

from Agent.OpenAIAgent import gpt_4o_openai_agent
from Utils.file_utils import load_file

load_dotenv()

version: str = os.environ['VERSION']

class PromptEngine:

    def __init__(self):
        prompt_dir = Path(__file__).parent / "SystemPrompts"
        self.prompt_templates = {
            'content_creation': load_file(str(prompt_dir / "basic_generation.txt"))
        }
    
    def generate_prompt_for_content_creation(self,
        customer_prompt: str,
        project_description: str, table: str, call_transcript: str, 
        topic: str, textbox_user_prompt: str, length: str   
    ) -> str:
        tables = [table]
        call_transcripts = [call_transcript]
        
        project_description_data = "The project description is: " + project_description
        table_data = "Our tables are: " + "\n".join(tables)
        call_transcripts_data = "\n".join(call_transcripts)
        topic_data = "Topic is: " + "\n" + topic
        textbox_user_prompt_data = "textbox_user_prompt: " + "\n" + textbox_user_prompt
        document_length = "The length of the analysis is: " + length

        collated_data = "\n".join(
                [customer_prompt, project_description_data, table_data, call_transcripts_data, topic_data, textbox_user_prompt_data, document_length]
        )
        return collated_data

    async def generate_content(self,
    customer_prompt_chain: list[dict],
    customer_prompt: str,
    project_description: str, table: str, call_transcript: str, 
    topic: str, textbox_user_prompt: str, length: str) -> tuple[Answer, list[dict]]:
        
        system_prompt = self.prompt_templates['content_creation']
        collated_data = self.generate_prompt_for_content_creation(
            customer_prompt, project_description, table, call_transcript, topic, textbox_user_prompt, length
        )
    

        prompt_chain = customer_prompt_chain + [{"role": "user", "content": collated_data}]
        answer = await gpt_4o_openai_agent(system_prompt, prompt_chain, Answer ,{})
        if answer:
            updated_prompt_chain = [*prompt_chain, {"role": "assistant", "content": 
                "Analysis generated: " + answer.analysis + "\n" + "Explanation: " + answer.explanation}]
            return answer, updated_prompt_chain
        else:
            raise Exception("No data generated")

    #@observe(capture_input=False, capture_output=False)
    #async def process_direct_match_response(self, seeker: Seeker, truthers: list[TableTruther], pdf_s3_file_name: str,
    #                                        agent: Agent) -> TableDirectMatch:
    #    
    #    langfuse_context.update_current_observation(
    #        name="process_direct_match_response",
    #        metadata={"seeker_ids": [seeker.textract_id]}
    #    )
    #    
    #    helicone_headers = {
    #        "Helicone-Property-pdf_s3_file_name": pdf_s3_file_name,
    #        "Helicone-Property-prompt-type": f"DirectMatch",
    #    }
#
#        prompt = self.generate_prompt_for_direct_matches(seeker, truthers)
#        
#        try:
#            system_prompt = self.prompt_templates['direct_match']
#            user_prompt = [{"role": "user", "content": prompt}]
#            match_response = await agent(system_prompt, user_prompt, DirectMatchResponse, helicone_headers)
#        except Exception as e:
#            print(f"[ERROR] Error processing direct match for seeker {seeker.textract_id}: {e}")
#            return TableDirectMatch(seeker, [])
#        if not match_response:
#            print(f"[ERROR] Error processing direct match for seeker {seeker.textract_id}")
#            return TableDirectMatch(seeker, [])
#        
#        truther_map = {t.textract_id: t for t in truthers}
#        t_matches: list[Tuple[TableTruther, str]] = []
#
#        for verification in match_response.verifications:
#            if verification.output.verification:
#                if verification.output.id in truther_map:
#                    t_matches.append((truther_map[verification.output.id], verification.output.reason))
#
#        return TableDirectMatch(seeker, t_matches)
#    
#    def generate_prompt_for_direct_matches(self, seeker: Seeker, truthers: list[TableTruther]) -> str:
#        # Group truthers by table
#        matching_truthers_by_table = {}
#        for truther in truthers:
#            if truther.table.table_chunk_textract_id not in matching_truthers_by_table:
#                matching_truthers_by_table[truther.table.table_chunk_textract_id] = []
#            matching_truthers_by_table[truther.table.table_chunk_textract_id].append(truther)
#
#        if seeker.is_table:
#            narrative_context = (
#                f"narrativeContext:\n"
#                f"    sectionTitle: \"{seeker.chunk.title}\"\n"
#                f"    coordinates:\n"
#                f"        columnTitle: \"{seeker.chunk.get_column_name(seeker.textract_id)}\"\n"
#                f"        rowTitle: \"{seeker.chunk.get_row_name(seeker.textract_id)}\"\n"
#                f"    verificationNumber:\n"
#                f"        verify_id: \"{seeker.textract_id}\"\n"
#                f"        value: \"{seeker.value}\"\n"
#                f"    verificationNumberInContext: |\n"
#                f"{seeker.chunk.to_salted_markdown([seeker.textract_id], 'verify_')}\n"
#            )
#        else:
#            narrative_context = (
#                f"narrativeContext:\n"
#                f"    sectionTitle: \"{seeker.chunk.header}\"\n"
#                f"    sectionSubtitle: \"{seeker.chunk.title}\"\n"
#                f"    verificationNumber:\n"
#                f"        verify_id: \"{seeker.textract_id}\"\n"
#                f"        value: \"{seeker.value}\"\n"
#                f"    verificationNumberInContext: |\n"
#                f"{seeker.chunk.generate_salted_text([seeker.textract_id], 'verify_')}\n"
#            )
#
#        table_contexts = []
#        for table_id, table_truthers in matching_truthers_by_table.items():
#            table = table_truthers[0].table
#            match_numbers = []
#            truther_ids = [t.textract_id for t in table_truthers]
#            
#            for truther in table_truthers:
#                match_numbers.append(
#                    f"      - match_id: \"{truther.textract_id}\"\n"
#                    f"        coordinates:\n"
#                    f"            columnTitle: \"{truther.column_name}\"\n"
#                    f"            rowTitle: \"{truther.row_name}\"\n"
#                    f"        value: \"{truther.value}\""
#                )
#            
#            table_context = (
#                f"  - sectionHeader: \"{table.header}\"\n"
#                f"    sectionTitle: \"{table.title}\"\n"
#                f"    tableTitle: \"{table.table_title}\"\n"
#                f"    matchNumbers:\n"
#                f"{chr(10).join(match_numbers)}\n"
#                f"    fullTableContext: |\n"
#                f"{table.to_salted_markdown(truther_ids, 'match_')}"
#            )
#            table_contexts.append(table_context)
#
#        return (
#            f"---\n"
#            f"{narrative_context}\n"
#            f"tableContexts:\n"
#            f"{chr(10).join(table_contexts)}\n"
#            f"---"
#        )


engine: PromptEngine = PromptEngine()