
import os
from google import genai
from google.genai import types
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

class AICertsImageGenerator:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def generate_and_save(
        self,
        brand_prompt: str,
        content_prompt: str,
        logo: Image.Image,
        output_path: str,
        model: str = "gemini-2.5-flash-image",
        aspect_ratio: str = "1:1",
    ):
        response = self.client.models.generate_content(
            model=model,
            contents=[brand_prompt, content_prompt, logo],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
            ),
        )

        for part in response.parts:
            if part.inline_data:
                image = part.as_image()
                image.save(output_path)
                return output_path

        raise RuntimeError("No image returned from Gemini")
