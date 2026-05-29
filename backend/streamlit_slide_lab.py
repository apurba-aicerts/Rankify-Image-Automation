"""
Local Streamlit UI for slide generation experiments (not used in Docker).

Uses the same prompt path as the HTTP API: :func:`~brands.demo_brand_template.build_demo_ai_certs_brand`
plus :mod:`generation.prompt_builder`.

Run from ``backend/``::

    streamlit run streamlit_slide_lab.py
"""

from __future__ import annotations

import logging
import os

import streamlit as st
from dotenv import load_dotenv
from PIL import Image

from brands.demo_brand_template import build_demo_ai_certs_brand
from gemini_slide_client import GeminiBrandImageClient
from generation.prompt_builder import build_governance_system_prompt, build_slide_user_prompt
from logging_config import configure_logging

load_dotenv()
configure_logging()
logger = logging.getLogger(__name__)
st.set_page_config(page_title="Rankify — Slide lab", layout="wide")

STREAMLIT_OUTPUT_SUBDIR = "outputs"
DEFAULT_LOGO_PATH = "assets/default_logo.jpg"

os.makedirs(STREAMLIT_OUTPUT_SUBDIR, exist_ok=True)

if "generated_images" not in st.session_state:
    st.session_state.generated_images = []

if "expanded_image" not in st.session_state:
    st.session_state.expanded_image = None

st.markdown(
    """
<style>
    .gallery-container {
        display: flex;
        flex-direction: column;
        gap: 30px;
        margin-top: 30px;
    }
    .thumbnail-container {
        border: 2px solid #e0e0e0;
        border-radius: 8px;
        padding: 10px;
        transition: all 0.3s ease;
        cursor: pointer;
        background: white;
    }
    .thumbnail-container:hover {
        border-color: #CFA935;
        box-shadow: 0 4px 12px rgba(207, 169, 53, 0.2);
        transform: translateY(-2px);
    }
    .stDownloadButton button {
        width: 100%;
        background-color: #CFA935;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 6px;
        font-weight: 500;
        transition: background-color 0.3s ease;
    }
    .stDownloadButton button:hover {
        background-color: #b8942e;
    }
    .expanded-image-container {
        position: relative;
        background: rgba(0, 0, 0, 0.05);
        border-radius: 12px;
        padding: 30px;
        margin: 20px 0;
    }
    .section-header {
        font-size: 24px;
        font-weight: 600;
        color: #1A1A2E;
        margin-bottom: 20px;
        border-bottom: 3px solid #CFA935;
        padding-bottom: 10px;
    }
    .image-label {
        text-align: center;
        font-weight: 500;
        color: #4D5060;
        margin-top: 8px;
        margin-bottom: 12px;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.sidebar.header("Configuration")

selected_model_id = st.sidebar.selectbox(
    "Gemini model",
    ("gemini-3-pro-image-preview", "gemini-2.5-flash-image"),
)

slide_count = st.sidebar.number_input(
    "Number of images",
    min_value=1,
    max_value=10,
    value=1,
)

aspect_ratio = st.sidebar.selectbox(
    "Aspect ratio",
    (
        "1:1",
        "2:3",
        "3:2",
        "3:4",
        "4:3",
        "4:5",
        "5:4",
        "9:16",
        "16:9",
        "21:9",
    ),
    index=0,
)

resolution_for_pro = None
if selected_model_id == "gemini-3-pro-image-preview":
    resolution_for_pro = st.sidebar.selectbox(
        "Image resolution",
        ("1K", "2K", "4K"),
        index=1,
    )
else:
    st.sidebar.info("Image size is managed automatically for the Flash model.")

uploaded_logo = st.sidebar.file_uploader(
    "Upload logo (optional)",
    type=["png", "jpg", "jpeg"],
)

if uploaded_logo:
    logo_image = Image.open(uploaded_logo)
else:
    logo_image = Image.open(DEFAULT_LOGO_PATH)

with st.sidebar:
    st.markdown("#### Logo in use")
    st.image(logo_image, width=80)

ESTIMATED_USD_PRICE_TABLE = {
    "gemini-2.5-flash-image": 0.039,
    "gemini-3-pro-image-preview": {
        "1K": 0.134,
        "2K": 0.134,
        "4K": 0.24,
    },
}


def estimate_usd_price_per_slide(model_id: str, resolution: str = "2K") -> float:
    """Static price hint for sidebar display (not live billing)."""
    if model_id == "gemini-3-pro-image-preview":
        return float(ESTIMATED_USD_PRICE_TABLE[model_id][resolution])
    return float(ESTIMATED_USD_PRICE_TABLE[model_id])


per_slide_usd = estimate_usd_price_per_slide(selected_model_id, resolution_for_pro or "2K")
total_usd = round(per_slide_usd * slide_count, 3)

with st.sidebar:
    st.markdown("### Estimated cost")
    st.metric("Per image (USD)", f"${per_slide_usd}")
    st.metric("Total (USD)", f"${total_usd}")
    st.caption("Estimated only; actual Google billing may differ.")

st.title("Rankify — carousel slide lab")

structured_post_copy = st.text_area(
    "Post content (strict format)",
    height=320,
    value="""TITLE:
Future-Proof Your Career with AI CERTs®

SUBTITLE:
Become Certified. Become AI-Ready.

BODY:
AI is transforming every industry.
Upskill with globally recognized, industry-aligned AI certifications
designed for professionals who want to stay ahead.

CTA BUTTON:
Enroll Now
""",
)

generate_clicked = st.button("Generate images", type="primary")

if generate_clicked:
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        st.error("GOOGLE_API_KEY not found in environment (.env)")
        st.stop()

    demo_cfg = build_demo_ai_certs_brand("streamlit-lab")
    governance_prompt = build_governance_system_prompt(demo_cfg)
    slide_user_prompt = build_slide_user_prompt(structured_post_copy, demo_cfg)

    client = GeminiBrandImageClient(google_api_key)

    st.session_state.generated_images = []
    st.session_state.expanded_image = None

    progress_bar = st.progress(0)
    status_text = st.empty()

    for index in range(1, slide_count + 1):
        status_text.text(f"Generating image {index} of {slide_count}...")
        output_path = os.path.join(STREAMLIT_OUTPUT_SUBDIR, f"rankify_playground_slide_{index}.png")

        client.generate_brand_slide_to_file(
            brand_governance_prompt=governance_prompt,
            slide_user_prompt=slide_user_prompt,
            logo=logo_image,
            output_file_path=output_path,
            model_id=selected_model_id,
            aspect_ratio=aspect_ratio,
            image_size=resolution_for_pro if selected_model_id == "gemini-3-pro-image-preview" else None,
        )

        st.session_state.generated_images.append(output_path)
        progress_bar.progress(index / slide_count)

    status_text.text("All images generated.")
    progress_bar.empty()
    logger.info(
        "Streamlit slide lab: generated %s image(s) model=%s aspect=%s",
        slide_count,
        selected_model_id,
        aspect_ratio,
    )

if st.session_state.generated_images:
    st.markdown("---")
    st.markdown(
        '<div class="section-header">Generated images</div>',
        unsafe_allow_html=True,
    )

    num_imgs = len(st.session_state.generated_images)
    if num_imgs <= 4:
        cols_count = 2
    elif num_imgs <= 9:
        cols_count = 3
    else:
        cols_count = 4

    if st.session_state.expanded_image is not None:
        expanded_idx = st.session_state.expanded_image
        expanded_path = st.session_state.generated_images[expanded_idx]

        st.markdown('<div class="expanded-image-container">', unsafe_allow_html=True)
        st.markdown(f"### Slide {expanded_idx + 1} — full size")
        st.image(expanded_path, use_container_width=True)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with open(expanded_path, "rb") as image_file:
                st.download_button(
                    label=f"Download slide {expanded_idx + 1}",
                    data=image_file,
                    file_name=os.path.basename(expanded_path),
                    mime="image/png",
                    key=f"download_expanded_{expanded_idx}",
                    use_container_width=True,
                )

        if st.button("Close full view", use_container_width=True):
            st.session_state.expanded_image = None
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("---")

    st.markdown("### Thumbnails")
    rows = (num_imgs + cols_count - 1) // cols_count

    img_idx = 0
    for _row in range(rows):
        cols = st.columns(cols_count)
        for _col_idx, col in enumerate(cols):
            if img_idx < num_imgs:
                img_path = st.session_state.generated_images[img_idx]
                with col:
                    st.markdown(
                        f'<div class="image-label">Slide {img_idx + 1}</div>',
                        unsafe_allow_html=True,
                    )
                    st.image(img_path, use_container_width=True)
                    with open(img_path, "rb") as image_file:
                        st.download_button(
                            label="Download",
                            data=image_file,
                            file_name=os.path.basename(img_path),
                            mime="image/png",
                            key=f"download_{img_idx}",
                            use_container_width=True,
                        )
                    st.markdown("<br>", unsafe_allow_html=True)
                img_idx += 1

    st.markdown("---")
    st.info(
        f"Total images: {num_imgs} | Model: {selected_model_id} | "
        f"Estimated: ${total_usd} (${per_slide_usd} per image)"
    )
