
import base64
import requests
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

class AICertsImageGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def _image_to_inline_data(self, image: Image.Image):
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return {
            "inlineData": {
                "mimeType": "image/png",
                "data": base64.b64encode(buffer.getvalue()).decode("utf-8"),
            }
        }

    def generate_and_save(
        self,
        brand_prompt: str,
        content_prompt: str,
        logo: Image.Image,
        output_path: str,
        model: str = "gemini-3-pro-image-preview",
        aspect_ratio: str = "1:1",
        image_size: str = "2K",
    ):
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{model}:generateContent"
            f"?key={self.api_key}"
        )

        contents = [
            {
                "parts": [
                    {"text": brand_prompt},
                    {"text": content_prompt},
                    self._image_to_inline_data(logo),
                ]
            }
        ]

        image_config = {
            "aspectRatio": aspect_ratio
        }

        if model == "gemini-3-pro-image-preview":
            image_config["image_size"] = image_size

        payload = {
            "contents": contents,
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": image_config,
            },
        }

        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()

        try:
            image_b64 = (
                data["candidates"][0]
                ["content"]["parts"][0]
                ["inlineData"]["data"]
            )
        except (KeyError, IndexError):
            raise RuntimeError(f"No image returned:\n{data}")

        image = Image.open(BytesIO(base64.b64decode(image_b64)))
        image.save(output_path)

        return output_path
