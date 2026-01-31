import os
import streamlit as st
from PIL import Image
from dotenv import load_dotenv

from generator import AICertsImageGenerator
from prompts import BRAND_PROMPT, build_content_prompt

# --------------------------------------------------
# Setup
# --------------------------------------------------
load_dotenv()
st.set_page_config(page_title="AI CERTs Image Generator", layout="wide")

OUTPUT_DIR = "outputs"
DEFAULT_LOGO_PATH = "assets/default_logo.jpg"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# --------------------------------------------------
# Session State
# --------------------------------------------------
if "generated_images" not in st.session_state:
    st.session_state.generated_images = []

if "expanded_image" not in st.session_state:
    st.session_state.expanded_image = None

# --------------------------------------------------
# CSS for Better Styling
# --------------------------------------------------
st.markdown("""
<style>
    /* Gallery container */
    .gallery-container {
        display: flex;
        flex-direction: column;
        gap: 30px;
        margin-top: 30px;
    }
    
    /* Thumbnail styling */
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
    
    /* Download button styling */
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
    
    /* Expanded image container */
    .expanded-image-container {
        position: relative;
        background: rgba(0, 0, 0, 0.05);
        border-radius: 12px;
        padding: 30px;
        margin: 20px 0;
    }
    
    /* Section headers */
    .section-header {
        font-size: 24px;
        font-weight: 600;
        color: #1A1A2E;
        margin-bottom: 20px;
        border-bottom: 3px solid #CFA935;
        padding-bottom: 10px;
    }
    
    /* Image label */
    .image-label {
        text-align: center;
        font-weight: 500;
        color: #4D5060;
        margin-top: 8px;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# Sidebar Configuration
# --------------------------------------------------
st.sidebar.header("⚙️ Configuration")

model_name = st.sidebar.selectbox(
    "Gemini Model",
    [
        "gemini-3-pro-image-preview",
        "gemini-2.5-flash-image"
    ],
)

num_images = st.sidebar.number_input(
    "Number of Images",
    min_value=1,
    max_value=10,
    value=1,
)


aspect_ratio = st.sidebar.selectbox(
    "Aspect Ratio",
    [
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
    ],
    index=0,
)

image_size = None

if model_name == "gemini-3-pro-image-preview":
    image_size = st.sidebar.selectbox(
        "Image Resolution",
        ["1K", "2K", "4K"],
        index=1,  # default = 2K
    )
else:
    st.sidebar.info("ℹ️ Image size is automatically managed for Flash model")

uploaded_logo = st.sidebar.file_uploader(
    "Upload Logo (Optional)",
    type=["png", "jpg", "jpeg"],
)

# --------------------------------------------------
# Logo Resolution
# --------------------------------------------------
if uploaded_logo:
    logo = Image.open(uploaded_logo)
else:
    logo = Image.open(DEFAULT_LOGO_PATH)

with st.sidebar:
    st.markdown("#### Logo In Use")
    st.image(logo, width=80)

# ----------------------------
# Pricing Table (Official)
# ----------------------------
PRICE_TABLE = {
    "gemini-2.5-flash-image": 0.039,  # fixed price per image
    "gemini-3-pro-image-preview": {
        "1K": 0.134,
        "2K": 0.134,
        "4K": 0.24,
    }
}

def get_image_price(model, resolution="2K"):
    if model == "gemini-3-pro-image-preview":
        return PRICE_TABLE[model][resolution]
    else:
        return PRICE_TABLE[model]
per_image_price = get_image_price(model_name, image_size or "2K")
total_price = round(per_image_price * num_images, 3)

with st.sidebar:
    st.markdown("### 💰 Estimated Cost")
    st.metric("Per Image (USD)", f"${per_image_price}")
    st.metric("Total Cost (USD)", f"${total_price}")
    st.caption("⚠️ Estimated cost. Actual billing may vary.")
    
# --------------------------------------------------
# Main UI
# --------------------------------------------------
st.title("🎨 AI CERTs® Carousel Image Generator")

content = st.text_area(
    "Post Content (STRICT FORMAT)",
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

generate_btn = st.button("🚀 Generate Images", type="primary")

# --------------------------------------------------
# Generation Logic
# --------------------------------------------------
if generate_btn:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        st.error("GOOGLE_API_KEY not found in .env")
        st.stop()

    generator = AICertsImageGenerator(api_key)
    content_prompt = build_content_prompt(content)

    st.session_state.generated_images = []
    st.session_state.expanded_image = None

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i in range(1, num_images + 1):
        status_text.text(f"Generating image {i} of {num_images}...")
        
        output_file = os.path.join(
            OUTPUT_DIR, f"aicerts_slide_{i}.png"
        )

        # generator.generate_and_save(
        #     brand_prompt=BRAND_PROMPT,
        #     content_prompt=content_prompt,
        #     logo=logo,
        #     model=model_name,
        #     output_path=output_file,
        # )
        generator.generate_and_save(
            brand_prompt=BRAND_PROMPT,
            content_prompt=content_prompt,
            logo=logo,
            model=model_name,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            output_path=output_file,
        )

        st.session_state.generated_images.append(output_file)
        progress_bar.progress(i / num_images)

    status_text.text("✅ All images generated successfully!")
    progress_bar.empty()

# --------------------------------------------------
# Display Images Gallery
# --------------------------------------------------
if st.session_state.generated_images:
    st.markdown("---")
    st.markdown('<div class="section-header">📸 Generated Images Gallery</div>', unsafe_allow_html=True)
    
    # Determine grid columns based on number of images
    num_imgs = len(st.session_state.generated_images)
    if num_imgs <= 4:
        cols_count = 2
    elif num_imgs <= 9:
        cols_count = 3
    else:
        cols_count = 4
    
    # Display expanded image if one is selected
    if st.session_state.expanded_image is not None:
        expanded_idx = st.session_state.expanded_image
        expanded_path = st.session_state.generated_images[expanded_idx]
        
        st.markdown('<div class="expanded-image-container">', unsafe_allow_html=True)
        st.markdown(f"### 🔍 Slide {expanded_idx + 1} - Full Size View")
        st.markdown("*Click outside the image to close*")
        
        # Display full-size image
        st.image(expanded_path, use_container_width=True)
        
        # Download button for expanded image
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with open(expanded_path, "rb") as f:
                st.download_button(
                    label=f"⬇️ Download Slide {expanded_idx + 1}",
                    data=f,
                    file_name=os.path.basename(expanded_path),
                    mime="image/png",
                    key=f"download_expanded_{expanded_idx}",
                    use_container_width=True
                )
        
        # Close button
        if st.button("✖️ Close Full View", use_container_width=True):
            st.session_state.expanded_image = None
            st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("---")
    
    # Thumbnail Grid
    st.markdown("### 🖼️ Thumbnail Gallery")
    st.markdown("*Click on any image to view full size*")
    
    # Create grid layout
    rows = (num_imgs + cols_count - 1) // cols_count  # Calculate number of rows needed
    
    img_idx = 0
    for row in range(rows):
        cols = st.columns(cols_count)
        
        for col_idx, col in enumerate(cols):
            if img_idx < num_imgs:
                img_path = st.session_state.generated_images[img_idx]
                
                with col:
                    # Image label
                    st.markdown(f'<div class="image-label">Slide {img_idx + 1}</div>', unsafe_allow_html=True)
                    
                    # Thumbnail image with click functionality
                    st.image(img_path, use_container_width=True)
                    
                    # # View Full Size button
                    # if st.button(f"🔍 View Full Size", key=f"view_{img_idx}", use_container_width=True):
                    #     st.session_state.expanded_image = img_idx
                    #     st.rerun()
                    
                    # Download button
                    with open(img_path, "rb") as f:
                        st.download_button(
                            label="⬇️ Download",
                            data=f,
                            file_name=os.path.basename(img_path),
                            mime="image/png",
                            key=f"download_{img_idx}",
                            use_container_width=True
                        )
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                
                img_idx += 1

    st.markdown("---")
    st.info(
        f"📊 Total images generated: {num_imgs} | "
        f"Model used: {model_name} | "
        f"Estimated price: ${total_price} "
        f"(${per_image_price} per image)"
    )

