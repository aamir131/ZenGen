import json
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any

from ExcelMaths.ExcelMaths import ExcelNumber
from Agent.Agent import Agent

class NumericNode:
    def __init__(self, numeric_node_id: int, chunk_id: int, ground_value: str, excel_number: ExcelNumber):
        self.numeric_node_id = numeric_node_id 
        self.chunk_id = chunk_id
        self.ground_value = ground_value
        self.excel_number = excel_number

class Truther(NumericNode):
    def __init__(self, truther_id: int, chunk_id: int, truther_value: str, truther_excel_number: ExcelNumber):
        super().__init__(truther_id, chunk_id, truther_value, truther_excel_number)
    
class Seeker(NumericNode):
    def __init__(self, seeker_id: int, chunk_id: int, seeker_value: str, seeker_excel_number: ExcelNumber):
        super().__init__(seeker_id, chunk_id, seeker_value, seeker_excel_number)

class ContentChunk(ABC):
    def __init__(self, chunk_id: int, child_blocks: list[dict[str, Any]], numeric_nodes: dict[int, NumericNode], 
                 header: str, footer: str, page_number: int):
        self.chunk_id: int = chunk_id
        self.child_blocks = child_blocks
        self.numeric_nodes: dict[int, NumericNode] = numeric_nodes
        self.header: str = header
        self.footer: str = footer
        self.page_number: int = page_number

    def saturated_salted_markdown(self) -> str:
        return self.salted_markdown(set(self.numeric_nodes.keys()))
    
    def markdown(self):
        return self.salted_markdown(set())

    @abstractmethod
    def salted_markdown(self, ids_to_salt: set[int]) -> str:
        raise NotImplementedError
    
    @abstractmethod
    def chunk_context(self) -> str:
        raise NotImplementedError
        
class TextChunk(ContentChunk):

    def __init__(self, chunk_id: int, word_blocks: list[dict[str, Any]], header, footer, page_number):
        for word_block in word_blocks:
            if "Id" not in word_block or "Text" not in word_block:
                raise ValueError(f"Word block {word_block} is not a valid word block")
        super().__init__(chunk_id, word_blocks, {node.numeric_node_id: node for node in self.extracted_numeric_nodes(chunk_id, word_blocks)}, 
                         header, footer, page_number)

        self.chunk_id: int = chunk_id
        self.word_blocks: list[dict[str, Any]] = word_blocks

    @staticmethod
    def extracted_numeric_nodes(chunk_id: int, word_blocks: list[dict[str, Any]]) -> list[NumericNode]:
        numeric_nodes = []

        for word_block in word_blocks:
            word_block_content_excel_number = ExcelNumber.is_excel_number(word_block['Text'])
            if word_block_content_excel_number:
                numeric_node = NumericNode(word_block['Id'], chunk_id, word_block['Text'], word_block_content_excel_number)
                numeric_nodes.append(numeric_node)
        return numeric_nodes
    
    def salted_markdown(self, ids_to_salt: set[int]) -> str:
        text = []
        for word in self.word_blocks:
            if word['Id'] in ids_to_salt:
                text.append(f"<id={word['Id']}/> {word['Text']}</>")
            else:
                text.append(word['Text'])
        return " ".join(text)
    
    def chunk_context(self):
        return ""

class TableChunk(ContentChunk):

    class TableCell(TextChunk):
        def __init__(self, chunk_id, cell_dict: dict[str, Any], header, footer, page_number):
            super().__init__(chunk_id, cell_dict['Content'], header, footer, page_number)
            self.cell_id = cell_dict['Id']
            self.cell_location = (cell_dict['RowIndex'], cell_dict['ColumnIndex'])

    def __init__(self, chunk_id: int, table_cells: list[dict[str, Any]], 
                 table_title: str,
                 section_header: str, table_footer: str,
                 bounding_box, page_number: int):

        self.chunk_id = chunk_id
        self.table = table_cells
        self.bounding_box = bounding_box
        self.table_title = table_title
        super().__init__(chunk_id, table_cells, {}, section_header, table_footer, page_number)

        cell_id_to_cell_dict, cell_location_to_cell_dict, numeric_nodes = self.extract_content_cells(table_cells)
        self.cell_id_to_cell_dict: dict[int, TableChunk.TableCell] = cell_id_to_cell_dict
        self.cell_location_to_cell_dict: dict[tuple[int, int], TableChunk.TableCell] = cell_location_to_cell_dict
        self.numeric_nodes: dict[int, NumericNode] = numeric_nodes

    def extract_content_cells(self, table_cells: list[dict[str, Any]]) -> tuple[dict[int, TableCell], dict[tuple[int, int], TableCell], dict[int, NumericNode]]:
        cell_id_to_cell_dict = {}
        cell_location_to_cell_dict = {}
        numeric_nodes: dict[int, NumericNode] = {}

        for cell in table_cells:
            if any([i not in cell for i in ["Id", "Content", "BoundingBox", "Type", "RowIndex", "ColumnIndex"]]):
                raise ValueError(f"Cell {cell} is not a valid table cell")
            table_cell = TableChunk.TableCell(self.chunk_id, cell, self.header, self.footer, self.page_number)
            cell_id_to_cell_dict[cell['Id']] = table_cell
            cell_location_to_cell_dict[(cell['RowIndex'], cell['ColumnIndex'])] = table_cell
            numeric_nodes.update(table_cell.numeric_nodes)
            
        return cell_id_to_cell_dict, cell_location_to_cell_dict, numeric_nodes
    
    def chunk_context(self):
           return (
            f"    sectionTitle: \"{self.header}\"\n"
            f"    tableTitle: \"{self.table_title}\"\n"
            f"    fullTableContext: |\n"
            f"{self.saturated_salted_markdown()}"
        )     
    
    def salted_markdown(self, ids_to_salt: set[int]) -> str:
        """Generate a markdown representation of the table, with specific IDs salted."""
        if not self.cell_location_to_cell_dict:
            return ""

        # Determine the number of rows and columns
        max_row = max(cell.cell_location[0] for cell in self.cell_location_to_cell_dict.values())
        max_col = max(cell.cell_location[1] for cell in self.cell_location_to_cell_dict.values())

        # Initialize table with empty strings
        table_data = [["" for _ in range(max_col + 1)] for _ in range(max_row + 1)]

        # Fill the table with cell content, applying salting using TextChunk's salted_markdown
        for (row, col), cell in self.cell_location_to_cell_dict.items():
            table_data[row][col] = cell.salted_markdown(ids_to_salt)

        # Find max column width for alignment
        col_widths = [max(len(row[col]) for row in table_data) for col in range(len(table_data[0]))]

        # Format rows with padding
        def format_row(row):
            return "| " + " | ".join(f"{cell:<{col_widths[i]}}" for i, cell in enumerate(row)) + " |"

        # Construct the markdown table
        markdown_table = [format_row(table_data[0])]  # Header row
        markdown_table.append("|" + "|".join(["-" * col_widths[i] for i in range(len(col_widths))]) + "|")  # Separator
        markdown_table.extend(format_row(row) for row in table_data[1:])  # Data rows

        return "\n".join(markdown_table)
    
class KnowledgeGraph:

    def __init__(self, text_chunks: list[TextChunk], table_chunks: list[TableChunk]):
        self.text_chunks = text_chunks
        self.table_chunks = table_chunks

        self.chunk_id_to_chunk: dict[int, ContentChunk] = {}
        for text_chunk in text_chunks:
            self.chunk_id_to_chunk[text_chunk.chunk_id] = text_chunk
        for table_chunk in table_chunks:
            self.chunk_id_to_chunk[table_chunk.chunk_id] = table_chunk

        self.truthers: dict[int, Truther] = KnowledgeGraph.create_truthers_from_table_chunks(table_chunks)
        self.seekers: dict[int, Seeker] = KnowledgeGraph.create_seekers_from_text_chunks(text_chunks)

        self.seeker_dependencies: dict[Seeker, list[Truther]] = {}
    
    @classmethod
    def create_seekers_from_text_chunks(cls, text_chunks: list[TextChunk]) -> dict[int, Seeker]:
        seekers: dict[int, Seeker] = {}
        for text_chunk in text_chunks:
            for numeric_node in text_chunk.numeric_nodes.values():
                seekers[numeric_node.numeric_node_id] = Seeker(
                    numeric_node.numeric_node_id, text_chunk.chunk_id,
                    numeric_node.ground_value, numeric_node.excel_number)
        return seekers

    @classmethod
    def create_truthers_from_table_chunks(cls, table_chunks: list[TableChunk]) -> dict[int, Truther]:
        truthers: dict[int, Truther] = {}
        for table_chunk in table_chunks:
            for table_cell in table_chunk.cell_location_to_cell_dict.values():
                for numeric_node in table_cell.numeric_nodes.values():
                    truthers[numeric_node.numeric_node_id] = Truther(
                        numeric_node.numeric_node_id, table_chunk.chunk_id,
                        numeric_node.ground_value, numeric_node.excel_number)
        return truthers
        
def generate_prompt_for_direct_matches_with_tables(seeker: Seeker, truthers: list[Truther], kg: KnowledgeGraph) -> str:
    chunk_to_truthers = {}
    for truther in truthers:
        if truther.chunk_id not in chunk_to_truthers:
            chunk_to_truthers[truther.chunk_id] = []
        chunk_to_truthers[truther.chunk_id].append(truthers)
    narrative_context = kg.chunk_id_to_chunk[seeker.chunk_id].salted_markdown({seeker.numeric_node_id})
    table_contexts = []
    for table_id, table_truthers in chunk_to_truthers.items():
        table = kg.chunk_id_to_chunk[table_id]
        table_contexts.append(table.chunk_context())

    return (
        f"---\n"
        f"narrativeContext:\n"
        f"{narrative_context}\n\n"
        f"tableContexts:\n"
        f"{(chr(10) * 2).join(table_contexts)}\n"
        f"---"
    )

def read_text_file(file_path):
    return open(file_path, 'r').read()

prompt_templates = {
    "direct_match": read_text_file("./PromptEngine/SystemPrompts/direct_match_prompt.txt")
}

class PairMatch(BaseModel):
    truther_id: int
    reason: str

class DirectMatchResponse(BaseModel):
    truther_matches: list[PairMatch]
    
async def process_direct_match_response(seeker: Seeker, truthers: list[Truther], 
                                        kg: KnowledgeGraph,
                                        pdf_s3_file_name: str,
                                        agent: Agent) -> type[DirectMatchResponse] | None:
    
    
    prompt = generate_prompt_for_direct_matches_with_tables(seeker, truthers, kg)
    
    helicone_headers = {
            "Helicone-Property-pdf_s3_file_name": pdf_s3_file_name,
            "Helicone-Property-prompt-type": f"DirectMatch",
    }
    
    try:
        system_prompt = prompt_templates['direct_match']
        user_prompt = [{"role": "user", "content": prompt}]
        llm_response = await agent(system_prompt, user_prompt, DirectMatchResponse, helicone_headers)
        return llm_response
    except:
        raise Exception