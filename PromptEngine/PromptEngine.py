import os, io, base64
from uuid import uuid4
from dotenv import load_dotenv
from typing import Tuple, Union, TypeVar
from pathlib import Path
from PIL import Image
from KG.SeekerTruther import ChartTruther

from PromptEngine.structured_output_types.structured_output_types import DirectMatchResponse, TopKTablesResponse, IndirectMatchResponse, ClusterMatchResponse, ClusterMatchOutput, IndirectMatchResponseV2, ChartToTableResponse, ChartToTable
from KG.SeekerTruther import Seeker
from PromptEngine.MatchTypes.TableMatch import TableDirectMatch, IndirectMatchV2
from KG.Chunks.TextChunk import TextChunk
from KG.Chunks.TableChunk import TableChunk, TableTruther
from PromptEngine.MatchTypes.ChartMatch import ChartDirectMatch

from langfuse.decorators import observe, langfuse_context

from Utils.s3_utils import s3_storage_buckets, get_image_from_s3, s3_client, get_image_object_from_s3
from Utils.image_snapshot import salt_page_with_chart_truthers, crop_image_from_textract_bounding_box

from Agent.Agent import Agent

load_dotenv()

version: str = os.environ['VERSION']

class PromptEngine:

    def __init__(self):
        prompt_dir = Path(__file__).parent / "SystemPrompts"
        self.prompt_templates = {
            'direct_match': self._load_file(prompt_dir / "direct_match_prompt.txt"),
        }

    def _load_file(self, file_path: Path) -> str:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()

    @observe(capture_input=False, capture_output=False)
    async def process_direct_match_response(self, seeker: Seeker, truthers: list[TableTruther], pdf_s3_file_name: str,
                                            agent: Agent) -> TableDirectMatch:
        
        langfuse_context.update_current_observation(
            name="process_direct_match_response",
            metadata={"seeker_ids": [seeker.textract_id]}
        )
        
        helicone_headers = {
            "Helicone-Property-pdf_s3_file_name": pdf_s3_file_name,
            "Helicone-Property-prompt-type": f"DirectMatch",
        }

        prompt = self.generate_prompt_for_direct_matches(seeker, truthers)
        
        try:
            system_prompt = self.prompt_templates['direct_match']
            user_prompt = [{"role": "user", "content": prompt}]
            match_response = await agent(system_prompt, user_prompt, DirectMatchResponse, helicone_headers)
        except Exception as e:
            print(f"[ERROR] Error processing direct match for seeker {seeker.textract_id}: {e}")
            return TableDirectMatch(seeker, [])
        if not match_response:
            print(f"[ERROR] Error processing direct match for seeker {seeker.textract_id}")
            return TableDirectMatch(seeker, [])
        
        truther_map = {t.textract_id: t for t in truthers}
        t_matches: list[Tuple[TableTruther, str]] = []

        for verification in match_response.verifications:
            if verification.output.verification:
                if verification.output.id in truther_map:
                    t_matches.append((truther_map[verification.output.id], verification.output.reason))

        return TableDirectMatch(seeker, t_matches)
    
    @observe(capture_input=False, capture_output=True)
    async def filter_top_k_tables(self, seekers: list[Seeker], table_chunks: dict[str, TableChunk], pdf_s3_file_name: str,
                                  agent: Agent) -> list[str]:

        chunk = seekers[0].chunk # All seekers are pre-filtered in the main function to be from the same chunk
        
        if seekers[0].is_table:
            narrative_text = (
                f"<narrativeText>\n"
                f"Section header: {chunk.header}\n"
                f"Section title: {chunk.title}\n"
                f"Page number: {chunk.page_number}\n"
                f"Subsection title: {chunk.table_title}\n"
                f"Narrative context:\n{chunk.to_salted_markdown([s.textract_id for s in seekers], 'verify_')}\n"
                f"</narrativeText>"
            )
        else:
            narrative_text = (
                f"<narrativeText>\n"
                f"Section header: {chunk.header}\n"
                f"Section title: {chunk.title}\n"
                f"Page number: {chunk.page_number}\n"
                f"Narrative: {chunk.generate_salted_text([s.textract_id for s in seekers], 'verify_')}\n"
                f"</narrativeText>"
            )

        tables_text = [
            (
                f"<table table_id={table_id}>\n"
                f"Table title: {table.table_title}\n"
                f"Page number: {table.page_number}\n"
                f"Row names: {table.metadata}\n"
                f"</table>\n\n"
            )
            for table_id, table in table_chunks.items()
        ]

        langfuse_context.update_current_observation(
            name="filter_top_k_tables",
            metadata={"seeker_ids": [s.textract_id for s in seekers]}
        )

        helicone_headers = {
            "Helicone-Property-pdf_s3_file_name": pdf_s3_file_name,
            "Helicone-Property-prompt-type": f"FilterTopKTables",
        }
        
        final_prompt = narrative_text + "\n\n" + "\n".join(tables_text)
        try:
            system_prompt = self.prompt_templates['filter_top_k']
            user_prompt = [{"role": "user", "content": final_prompt}]
            response = await agent(system_prompt, user_prompt, TopKTablesResponse, helicone_headers)
            if not response:
                print(f"[ERROR] Error processing top k tables filter for seeker {seekers[0].textract_id}")
                return []
            return response.table_ids
        except Exception as e:
            print(f"[ERROR] Error processing top k tables filter for seeker {seekers[0].textract_id}: {e}")
            return []

    def generate_prompt_for_direct_matches(self, seeker: Seeker, truthers: list[TableTruther]) -> str:
        # Group truthers by table
        matching_truthers_by_table = {}
        for truther in truthers:
            if truther.table.table_chunk_textract_id not in matching_truthers_by_table:
                matching_truthers_by_table[truther.table.table_chunk_textract_id] = []
            matching_truthers_by_table[truther.table.table_chunk_textract_id].append(truther)

        if seeker.is_table:
            narrative_context = (
                f"narrativeContext:\n"
                f"    sectionTitle: \"{seeker.chunk.title}\"\n"
                f"    coordinates:\n"
                f"        columnTitle: \"{seeker.chunk.get_column_name(seeker.textract_id)}\"\n"
                f"        rowTitle: \"{seeker.chunk.get_row_name(seeker.textract_id)}\"\n"
                f"    verificationNumber:\n"
                f"        verify_id: \"{seeker.textract_id}\"\n"
                f"        value: \"{seeker.value}\"\n"
                f"    verificationNumberInContext: |\n"
                f"{seeker.chunk.to_salted_markdown([seeker.textract_id], 'verify_')}\n"
            )
        else:
            narrative_context = (
                f"narrativeContext:\n"
                f"    sectionTitle: \"{seeker.chunk.header}\"\n"
                f"    sectionSubtitle: \"{seeker.chunk.title}\"\n"
                f"    verificationNumber:\n"
                f"        verify_id: \"{seeker.textract_id}\"\n"
                f"        value: \"{seeker.value}\"\n"
                f"    verificationNumberInContext: |\n"
                f"{seeker.chunk.generate_salted_text([seeker.textract_id], 'verify_')}\n"
            )

        table_contexts = []
        for table_id, table_truthers in matching_truthers_by_table.items():
            table = table_truthers[0].table
            match_numbers = []
            truther_ids = [t.textract_id for t in table_truthers]
            
            for truther in table_truthers:
                match_numbers.append(
                    f"      - match_id: \"{truther.textract_id}\"\n"
                    f"        coordinates:\n"
                    f"            columnTitle: \"{truther.column_name}\"\n"
                    f"            rowTitle: \"{truther.row_name}\"\n"
                    f"        value: \"{truther.value}\""
                )
            
            table_context = (
                f"  - sectionHeader: \"{table.header}\"\n"
                f"    sectionTitle: \"{table.title}\"\n"
                f"    tableTitle: \"{table.table_title}\"\n"
                f"    matchNumbers:\n"
                f"{chr(10).join(match_numbers)}\n"
                f"    fullTableContext: |\n"
                f"{table.to_salted_markdown(truther_ids, 'match_')}"
            )
            table_contexts.append(table_context)

        return (
            f"---\n"
            f"{narrative_context}\n"
            f"tableContexts:\n"
            f"{chr(10).join(table_contexts)}\n"
            f"---"
        )

    def generate_prompt_for_indirect_matches(self, chunk: Union[TextChunk, TableChunk], non_direct_seekers: list[Seeker], all_truthers: dict[str, TableTruther], selected_table_chunks: dict[str, TableChunk]) -> str:

        if isinstance(chunk, TableChunk):
            narrative_text = (
                f"<narrativeText>\n"
                f"Section header: {chunk.header}\n"
                f"Section title: {chunk.title}\n"
                f"Page number: {chunk.page_number}\n"
                f"Subsection title: {chunk.table_title}\n"
                f"Narrative context:\n{chunk.to_salted_markdown([s.textract_id for s in non_direct_seekers], 'verify_')}\n"
                f"</narrativeText>"
            )
        else:
            narrative_text = (
                f"<narrativeText>\n"
                f"Section header: {chunk.header}\n"
                f"Section title: {chunk.title}\n"
                f"Page number: {chunk.page_number}\n"
                f"Narrative: {chunk.generate_salted_text([s.textract_id for s in non_direct_seekers], 'verify_')}\n"
                f"</narrativeText>"
            )

        tables_text = [
            (
                f"<table tableId={table_id}>\n"
                f"Table title: {table.table_title}\n"
                f"Page number: {table.page_number}\n"
                f"Table content:\n{table.to_salted_markdown([t.textract_id for t in all_truthers.values()])}\n"
                f"</table>"
            )
            for table_id, table in selected_table_chunks.items()
        ]
        
        return narrative_text + "\n\n" + "\n".join(tables_text)
    
    def generate_prompt_for_cluster_matches(self, seekers: list[Seeker]) -> str:
        narrative_contexts = []  # List to store all contexts
        
        for seeker in seekers:
            if seeker.is_table:
                narrative_context = (
                    f"narrativeContext:\n"
                    f"    pageNumber: \"{seeker.chunk.page_number}\"\n"
                    f"    sectionTitle: \"{seeker.chunk.title}\"\n"
                    f"    coordinates:\n"
                    f"        columnTitle: \"{seeker.chunk.get_column_name(seeker.textract_id)}\"\n"
                    f"        rowTitle: \"{seeker.chunk.get_row_name(seeker.textract_id)}\"\n"
                    f"    linkNumber:\n"
                    f"        link_id: \"{seeker.textract_id}\"\n"
                    f"        value: \"{seeker.value}\"\n"
                    f"    linkNumberInContext: |\n"
                    f"{seeker.chunk.to_salted_markdown([seeker.textract_id], 'link_')}\n"
                )
            else:
                narrative_context = (
                    f"narrativeContext:\n"
                    f"    pageNumber: \"{seeker.chunk.page_number}\"\n"
                    f"    sectionTitle: \"{seeker.chunk.header}\"\n"
                    f"    sectionSubtitle: \"{seeker.chunk.title}\"\n"
                    f"    linkNumber:\n"
                    f"        link_id: \"{seeker.textract_id}\"\n"
                    f"        value: \"{seeker.value}\"\n"
                    f"    linkNumberInContext: |\n"
                    f"{seeker.chunk.generate_salted_text([seeker.textract_id], 'link_')}\n"
                )
            narrative_contexts.append(narrative_context)

        # Join all contexts with separators
        return (
            "---\n" + 
            "\n---\n".join(narrative_contexts) + 
            "\n---"
        )

    @observe(capture_input=False, capture_output=False)
    async def process_cluster_match_response(self, seekers: list[Seeker], pdf_s3_file_name: str,
                                             agent: Agent) -> list[ClusterMatchOutput]:

        langfuse_context.update_current_observation(
            name="process_cluster_match_response",
            metadata={"seeker_ids": [s.textract_id for s in seekers]}
        )

        helicone_headers = {
            "Helicone-Property-prompt-type": f"Clustering",
            "Helicone-Property-pdf_s3_file_name": pdf_s3_file_name,
        }

        prompt = self.generate_prompt_for_cluster_matches(seekers)
        try:
            system_prompt = self.prompt_templates['cluster_match']
            user_prompt = [{"role": "user", "content": prompt}]
            match_response = await agent(system_prompt, user_prompt, ClusterMatchResponse, helicone_headers)
            if match_response:
                return match_response.hyperlinks
            else:
                print(f"[ERROR] Error processing cluster match for seekers {', '.join([s.textract_id for s in seekers])}. No Exception thrown")
                return []
        except Exception as e:
            print(f"[ERROR] Error processing cluster match for seekers {', '.join([s.textract_id for s in seekers])}: {e}")
            return []

    @observe(capture_input=False, capture_output=False)
    async def process_indirect_match_response_v2(self, chunk: Union[TextChunk, TableChunk], non_direct_seekers: dict[str, Seeker], 
                                  all_truthers: dict[str, TableTruther], selected_table_chunks: dict[str, TableChunk], pdf_s3_file_name: str, agent: Agent) -> list[IndirectMatchResponseV2]:
    
        langfuse_context.update_current_observation(
            name="process_indirect_match_response_v2",
            metadata={"seeker_ids": [s.textract_id for s in non_direct_seekers.values()]}
        )

        helicone_headers = {
            "Helicone-Property-pdf_s3_file_name": pdf_s3_file_name,
            "Helicone-Property-prompt-type": f"IndirectMatchV2",
        }

        prompt = self.generate_prompt_for_indirect_matches(chunk, list(non_direct_seekers.values()), all_truthers, selected_table_chunks)

        try:
            system_prompt = self.prompt_templates['get_calculation']
            user_prompt = [{"role": "user", "content": prompt}]
            response = await agent(system_prompt, user_prompt, IndirectMatchResponseV2, helicone_headers)
        except Exception as e:
            print(f"[ERROR] Error processing indirect match v2 for chunk {chunk.title}: {e}")
            return []
        if not response:
            print(f"[ERROR] Error processing indirect match v2 for chunk {chunk.title}. No Exception too")
            return []

        # Process and validate matches
        indirect_matches = {}
        for match in response.matches:
            # Validate seeker exists
            if match.verify_id not in non_direct_seekers:
                print(f"[ERROR] Warning: Seeker ID {match.verify_id} not found in non_direct_seekers")
                continue

            # Validate all references exist
            valid_references = []
            for ref in match.calculation.references:
                if ref.reference_id in all_truthers:
                    valid_references.append(ref)
                else:
                    print(f"[ERROR] Warning: Truther ID {ref.reference_id} not found for seeker {match.verify_id}")

            # Create IndirectMatchV2 instance with validated data
            seeker = non_direct_seekers[match.verify_id]
            indirect_match = IndirectMatchV2(
                s=seeker,
                verify_id=match.verify_id,
                long_reasoning=match.long_reasoning,
                derivable=match.derivable,
                reason=match.reason,
                calculation_formula=match.calculation.formula,
                calculation_references=[
                    {"variable_name": ref.variable_name, "reference_id": ref.reference_id}
                    for ref in valid_references
                ]
            )

            indirect_matches[match.verify_id] = indirect_match

        return list(indirect_matches.values())
    
    def generate_prompt_for_chart_direct_match(self, seeker: Seeker, chart_truthers: list[ChartTruther]) -> str:

        matching_truthers_by_chart = {}
        for truther in chart_truthers:
            if truther.chart_id not in matching_truthers_by_chart:
                matching_truthers_by_chart[truther.chart_id] = []
            matching_truthers_by_chart[truther.chart_id].append(truther)

        if seeker.is_table:
            narrative_context = (
                f"narrativeContext:\n"
                f"    sectionTitle: \"{seeker.chunk.title}\"\n"
                f"    coordinates:\n"
                f"        columnTitle: \"{seeker.chunk.get_column_name(seeker.textract_id)}\"\n"
                f"        rowTitle: \"{seeker.chunk.get_row_name(seeker.textract_id)}\"\n"
                f"    verificationNumber:\n"
                f"        verify_id: \"{seeker.textract_id}\"\n"
                f"        value: \"{seeker.value}\"\n"
                f"    verificationNumberInContext: |\n"
                f"{seeker.chunk.to_salted_markdown([seeker.textract_id], 'verify_')}\n"
            )
        else:
            narrative_context = (
                f"narrativeContext:\n"
                f"    sectionTitle: \"{seeker.chunk.header}\"\n"
                f"    sectionSubtitle: \"{seeker.chunk.title}\"\n"
                f"    verificationNumber:\n"
                f"        verify_id: \"{seeker.textract_id}\"\n"
                f"        value: \"{seeker.value}\"\n"
                f"    verificationNumberInContext: |\n"
                f"{seeker.chunk.generate_salted_text([seeker.textract_id], 'verify_')}\n"
            )

        chart_contexts = []
        for chart_id, chart_truthers in matching_truthers_by_chart.items():
            chart = chart_truthers[0].chart_chunk
            match_numbers = []
            chart_truther_ids = [t.textract_id for t in chart_truthers]

            for truther in chart_truthers:
                match_numbers.append(
                    f"      - match_id: \"{truther.textract_id}\"\n"
                    f"        value: \"{truther.value}\""
                )

            chart_context = (
                f"    chartTitle: \"{chart.chart_title}\"\n"
                f"    matchNumbers:\n"
                f"{chr(10).join(match_numbers)}\n"
                f"    fullChartContext: |\n"
                f"{chart.to_salted_markdown(chart_truther_ids, 'match_')}"
#                f"    notesToChart: |\n"
#                f"{chart.notes_to_chart}"
            )
            chart_contexts.append(chart_context)

        return (
            f"---\n"
            f"{narrative_context}\n"
            f"chartContexts:\n"
            f"{chr(10).join(chart_contexts)}\n"
            f"---"
        )

    @observe(capture_input=False, capture_output=False)
    async def process_chart_direct_match_response(self, seeker: Seeker, chart_truthers: list[ChartTruther], pdf_s3_file_name: str, agent: Agent) -> ChartDirectMatch:

        
        langfuse_context.update_current_observation(
            name="process_chart_direct_match_response",
            metadata={"seeker_ids": seeker.textract_id}
        )

        helicone_headers = {
            "Helicone-Property-pdf_s3_file_name": pdf_s3_file_name,
            "Helicone-Property-prompt-type": f"ChartDirectMatch",
        }

        prompt = self.generate_prompt_for_chart_direct_match(seeker, chart_truthers)

        try:
            system_prompt = self.prompt_templates['chart_direct_match']
            user_prompt = [{"role": "user", "content": prompt}]
            match_response = await agent(system_prompt, user_prompt, DirectMatchResponse, helicone_headers)
        except Exception as e:
            print(f"[ERROR] Error processing chart direct match for seeker {seeker.textract_id}: {e}")
            return ChartDirectMatch(seeker, [])
        if not match_response:
            print(f"[ERROR] Error processing chart direct match for seeker {seeker.textract_id}")
            return ChartDirectMatch(seeker, [])

        truther_map = {t.textract_id: t for t in chart_truthers}
        t_matches: list[Tuple[ChartTruther, str]] = []

        for verification in match_response.verifications:
            if verification.output.verification:
                if verification.output.id in truther_map:
                    t_matches.append((truther_map[verification.output.id], verification.output.reason))

        return ChartDirectMatch(seeker, t_matches)
    
    def generate_prompt_for_figure_to_chart_conversion(self, s3_init_parsing_bucket: s3_storage_buckets,
                                                       full_page_key: str, figure_folders: str,
                                                       possible_chart_truthers_textract_id_to_uuid: dict[str, str],
                                                       textract_response_dict: dict[str, dict],
                                                       page_number: int) -> list:
        messages = []
        full_page_base64 = get_image_from_s3(s3_init_parsing_bucket, full_page_key)

        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Full screenshot of page for context:"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{full_page_base64}"
                    }
                }
            ]
        })

        response = s3_client.list_objects_v2(
            Bucket=s3_init_parsing_bucket.value.name,
            Prefix=figure_folders
        )

        figure_keys = [obj['Key'] for obj in response.get('Contents', [])]
        page_object: Image.Image = get_image_object_from_s3(s3_init_parsing_bucket, full_page_key)
        page_width, page_height = page_object.height, page_object.width
        salted_page = salt_page_with_chart_truthers(page_object, possible_chart_truthers_textract_id_to_uuid, textract_response_dict, page_number)

        for key in figure_keys:
            fig_id = key.split('/')[-1].replace('.png', '').replace('fig_', '')

            #figure_object: Image.Image = get_image_object_from_s3(s3_init_parsing_bucket, key)
            #figure_object = salt_image_with_chart_truthers(figure_object, fig_id, page_width, page_height,
            #                                               possible_chart_truthers_textract_id_to_uuid, textract_response_dict, page_number)

            figure_img = crop_image_from_textract_bounding_box(salted_page, textract_response_dict[fig_id]['Geometry']['BoundingBox'])
            with io.BytesIO() as buffer:
                figure_img.save(buffer, format='PNG', optimize=True, quality=85)
                figure_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Figure with id {fig_id}:"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{figure_base64}"
                        }
                    }
                ]
            })

        return messages
    
    @observe(capture_input=False, capture_output=False)
    async def process_figure_to_chart_conversion(self, file_hash: str, s3_init_parsing_bucket: s3_storage_buckets, 
                                                 page_number: int, 
                                                 textract_response_dict: dict[str, dict], 
                                                 possible_chart_truthers_uuid_to_textract_id: dict[str, str],
                                                 possible_chart_truthers_textract_id_to_uuid: dict[str, str],
                                                 agent: Agent) -> list[ChartToTable]:

        langfuse_context.update_current_observation(
            name="process_figure_to_chart_conversion",
            metadata={"page_number": page_number}
        )

        helicone_headers = {
            "Helicone-Property-prompt-type": f"figure_to_chart_conversion",
            "Helicone-Property-pdf_s3_file_name": file_hash,
        }
        try:
            system_prompt = self.prompt_templates['figure_to_chart_conversion']
            user_prompt = self.generate_prompt_for_figure_to_chart_conversion(
                s3_init_parsing_bucket, 
                f"{file_hash}/versions/{version}/Screenshots/full_pages/page_{page_number}.png",
                f"{file_hash}/versions/{version}/Screenshots/page_{page_number}_figures", 
                possible_chart_truthers_textract_id_to_uuid,
                textract_response_dict,
                page_number
            )
            response: ChartToTableResponse | None = await agent(system_prompt, user_prompt, ChartToTableResponse, helicone_headers)
            if response:
                #for chart in response.charts:
                #    for chart_truther_uuid in possible_chart_truthers_uuid_to_textract_id.keys():
                #        rep = f'<id="{chart_truther_uuid}">{possible_chart_truthers_uuid_to_textract_id[chart_truther_uuid]}</>'
                #        chart.table = chart.table.replace(chart_truther_uuid, rep)
                return response.charts
            else:
                print(f"[ERROR] Error processing figure to chart conversion for page {page_number}. No exception thrown")
                return []
        except Exception as e:
            print(f"[ERROR] Error processing figure to chart conversion for page {page_number}: {e}")
            return []

engine: PromptEngine = PromptEngine()