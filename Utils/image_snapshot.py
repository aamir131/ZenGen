import io, os
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
from KG.SeekerTruther import ChartTruther

from Utils.s3_utils import s3_storage_buckets, save_png_to_s3, s3_client

load_dotenv()
version: str = os.environ['VERSION']

def _create_pixmap_image(page, matrix, clip_rect=None):
    """
    Helper function to create a PNG image from a page pixmap.
    """
    try:
        pix = page.get_pixmap(matrix=matrix, clip=clip_rect, alpha=False)
        if not pix:
            raise Exception("Failed to create pixmap")

        width, height = pix.width, pix.height
        if width <= 0 or height <= 0:
            raise Exception(f"Invalid pixmap dimensions: {width}x{height}")

        img = Image.frombuffer("RGB", (width, height), pix.samples)
        with io.BytesIO() as img_byte_arr:
            img.save(img_byte_arr, format='PNG', optimize=True)
            return img_byte_arr.getvalue()

    except Exception as e:
        raise Exception(f"Error creating pixmap image: {str(e)}")
    
def save_full_page_screenshot(pdf_doc, page_num):
    """Creates a full page screenshot."""
    page = pdf_doc[page_num - 1]
    return _create_pixmap_image(page, fitz.Matrix(2, 2))

def create_image_from_bbox_percent(pdf_doc, page_num, geometry, padding=0.0):
    """Creates an image from a PDF page based on bounding box coordinates."""
    page = pdf_doc[page_num - 1]
    bbox = geometry["BoundingBox"]

    width = bbox["Width"]
    height = bbox["Height"]
    left = bbox["Left"]
    top = bbox["Top"]

    padding_height = height * padding
    new_top = max(0, top - padding_height)
    new_height = min(1.0 - new_top, height + (2 * padding_height))

    rect = fitz.Rect(
        left * page.rect.width,
        new_top * page.rect.height,
        (left + width) * page.rect.width,
        (new_top + new_height) * page.rect.height
    )

    return _create_pixmap_image(page, fitz.Matrix(2, 2), rect)

def has_numeric_text(block, textract_response):
    """Check if block contains numeric text in its children."""
    if 'Relationships' not in block:
        return False

    for rel in block['Relationships']:
        if rel['Type'] != "CHILD":
            continue

        for child_id in rel['Ids']:
            child_block = next(
                (b for b in textract_response['Blocks'] if b['Id'] == child_id),
                None
            )
            if child_block and 'Text' in child_block:
                if any(char.isdigit() for char in child_block['Text']):
                    return True
    return False

async def save_full_page_and_figures_to_s3(textract_response, 
                                           pdf_s3_file_name: str, 
                                           file_hash: str, s3_uploads_bucket: s3_storage_buckets, s3_init_parsing_bucket: s3_storage_buckets, page_num):
    try:
        pdf_obj = s3_client.get_object(Bucket=s3_uploads_bucket.value.name, Key=pdf_s3_file_name)
        pdf_data = pdf_obj['Body'].read()
        if not pdf_data:
            raise Exception("Downloaded PDF data is empty")

        pdf_doc = fitz.open(stream=pdf_data, filetype="pdf")
        if not pdf_doc:
            raise Exception("Failed to create PDF document object")

        number_of_figures_on_page = 0
        try:
            screenshot_folder_key: str = f"{file_hash}/versions/{version}/Screenshots"

            full_page_img = save_full_page_screenshot(pdf_doc, page_num)
            save_png_to_s3(s3_init_parsing_bucket, f"{screenshot_folder_key}/full_pages", f"page_{page_num}.png", full_page_img)

            for block in textract_response['Blocks']:
                if (block['BlockType'] == "LAYOUT_FIGURE" and 
                    block.get('Page', 1) == page_num and 
                    has_numeric_text(block, textract_response)):

                    number_of_figures_on_page += 1
                    figure_img = create_image_from_bbox_percent(pdf_doc, page_num, block['Geometry'])
                    save_png_to_s3(s3_init_parsing_bucket, f"{screenshot_folder_key}/page_{page_num}_figures", f"fig_{block['Id']}.png", figure_img)

        finally:
            pdf_doc.close()
            return number_of_figures_on_page

    except Exception as e:
        print(f"[ERROR] Failed to process figures for page {page_num}: {str(e)}")
        raise e

def salt_page_with_chart_truthers(page: Image.Image, possible_chart_truthers_textract_id_to_uuid: dict[str, str], textract_response_dict: dict[str, dict], page_number: int) -> Image.Image:
    draw = ImageDraw.Draw(page)
    font = ImageFont.load_default(size=20)

    page_height, page_width = page.width, page.height
    for textract_id, chart_truther_uuid in possible_chart_truthers_textract_id_to_uuid.items():
        if textract_response_dict[textract_id]['Page'] != page_number:
            continue

        bounding_box = textract_response_dict[textract_id]['Geometry']['BoundingBox']
        rect_coords = (bounding_box['Left'] * page_height, bounding_box['Top'] * page_width, 
                       (bounding_box['Left'] + bounding_box['Width']) * page_height, 
                       (bounding_box['Top'] + bounding_box['Height']) * page_width)
        draw.rectangle(rect_coords, fill="white")  # Draw a white rectangle
        draw.text((rect_coords[0], rect_coords[1]), chart_truther_uuid, fill="black", font=font)
    return page

def salt_image_with_chart_truthers(figure_image: Image.Image, 
                                   fig_id: str,
                                   page_width: int,
                                   page_height: int,
                                   possible_chart_truthers_textract_id_to_uuid: dict[str, str], 
                                   textract_response_dict: dict[str, dict],
                                   page_number: int) -> Image.Image:
    draw = ImageDraw.Draw(figure_image)
    font = ImageFont.load_default(size=20)

    figure_left = textract_response_dict[fig_id]['Geometry']['BoundingBox']['Left']
    figure_top = textract_response_dict[fig_id]['Geometry']['BoundingBox']['Top']
    figure_width = textract_response_dict[fig_id]['Geometry']['BoundingBox']['Width']
    figure_height = textract_response_dict[fig_id]['Geometry']['BoundingBox']['Height']

    figure_rectangle = (figure_left * page_height, figure_top * page_width, 
                        (figure_left + figure_width) * page_height, 
                        (figure_top + figure_height) * page_width)

    for textract_id, chart_truther_uuid in possible_chart_truthers_textract_id_to_uuid.items():
        chart_truther_top_left = (textract_response_dict[textract_id]['Geometry']['BoundingBox']['Left'] * figure_image.height, 
                                  textract_response_dict[textract_id]['Geometry']['BoundingBox']['Top'] * figure_image.width)
        if textract_response_dict[textract_id]['Page'] != page_number:
            continue

        bounding_box = textract_response_dict[textract_id]['Geometry']['BoundingBox']
        rect_coords = (bounding_box['Left'] * figure_image.height, bounding_box['Top'] * figure_image.width, 
                       (bounding_box['Left'] + bounding_box['Width']) * figure_image.height, 
                       (bounding_box['Top'] + bounding_box['Height']) * figure_image.width)
        draw.rectangle(rect_coords, fill="white")  # Draw a white rectangle
        draw.text((rect_coords[0], rect_coords[1]), chart_truther_uuid, fill="black", font=font)
    return figure_image

def crop_image_from_textract_bounding_box(image: Image.Image, bounding_box: dict) -> Image.Image:
    img_width, img_height = image.size

    left = int(bounding_box["Left"] * img_width)
    top = int(bounding_box["Top"] * img_height)
    width = int(bounding_box["Width"] * img_width)
    height = int(bounding_box["Height"] * img_height)

    right = left + width
    bottom = top + height

    cropped_img = image.crop((left, top, right, bottom))

    return cropped_img