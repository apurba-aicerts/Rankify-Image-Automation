# 🎨 AI CERTs® Carousel Image Generator

A professional social media carousel image generator powered by Google's Gemini AI, specifically designed for AI CERTs® brand-compliant LinkedIn and social media posts.

🔗 **Live Demo**: [https://rankifyimg.aicerts.ai/](https://rankifyimg.aicerts.ai/)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [For General Users](#for-general-users)
  - [For Developers](#for-developers)
- [Project Structure](#project-structure)
- [Brand Guidelines](#brand-guidelines)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## 🌟 Overview

The AI CERTs® Carousel Image Generator is a Streamlit-based web application that automatically creates professional, brand-compliant social media carousel images. It uses Google's Gemini AI models to generate visually stunning posts that adhere to AI CERTs® official brand guidelines.

### Key Highlights

- ✅ **Brand-Compliant**: Automatically follows AI CERTs® color schemes, typography, and layout rules
- 🤖 **AI-Powered**: Leverages Google Gemini's advanced image generation capabilities
- 🎯 **Template-Based**: Uses structured content format for consistent outputs
- 🖼️ **Batch Generation**: Generate multiple variations in a single click
- 📱 **1080x1080**: Optimized for Instagram, LinkedIn, and Facebook carousels

---

## ✨ Features

### For Users

- 🎨 **Automated Design**: No design skills required—just provide content
- 🏷️ **Custom Logo Support**: Upload your own logo or use the default
- 📊 **Batch Processing**: Generate 1-10 images at once
- 🖼️ **Interactive Gallery**: View thumbnails and full-size previews
- ⬇️ **Easy Downloads**: One-click download for all generated images
- 🎯 **Brand Consistency**: Every image follows AI CERTs® guidelines

### For Developers

- 🔧 **Modular Architecture**: Separated concerns (UI, generation, prompts)
- 🚀 **Easy Integration**: Simple API-based image generation
- 📝 **Customizable Prompts**: Easily modify brand guidelines and content templates
- 🔄 **Multiple Models**: Support for different Gemini models
- 💾 **Session Management**: Streamlit state handling for seamless UX

---

## 🛠️ Prerequisites

Before you begin, ensure you have the following installed:

- **Python**: Version 3.8 or higher
- **pip**: Python package manager
- **Google API Key**: For Gemini AI access ([Get one here](https://aistudio.google.com/app/apikey))

---

## 📦 Installation

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd ai-certs-image-generator
```

### Step 2: Create Virtual Environment (Recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Required packages:**
```
streamlit
google-genai
pillow
python-dotenv
```

### Step 4: Create `.env` File

Create a `.env` file in the project root:

```bash
GOOGLE_API_KEY=your_google_api_key_here
```

Replace `your_google_api_key_here` with your actual Google API key.

---

## ⚙️ Configuration

### Directory Structure Setup

The application automatically creates necessary directories, but you can set them up manually:

```bash
mkdir outputs
mkdir assets
```

### Default Logo

Place your default logo at:
```
assets/default_logo.jpg
```

If no logo is present, the app will prompt you to upload one.

---

## 🚀 Usage

### For General Users

#### Step 1: Launch the Application

```bash
streamlit run app.py
```

The app will open in your default browser at `http://localhost:8501`

#### Step 2: Configure Settings (Sidebar)

1. **Select Gemini Model**:
   - `gemini-3-pro-image-preview` (High quality, slower)
   - `gemini-2.5-flash-image` (Faster, good quality)

2. **Set Number of Images**:
   - Choose between 1-10 images
   - More images = more variety

3. **Upload Logo** (Optional):
   - Click "Browse files"
   - Select PNG, JPG, or JPEG
   - Or use the default AI CERTs® logo

#### Step 3: Enter Content

Use the **STRICT FORMAT** in the text area:

```
TITLE:
Your Main Headline Here

SUBTITLE:
Your Supporting Headline

BODY:
Your main message text.
Can be multiple lines.
Keep it concise and impactful.

CTA BUTTON:
Your Call-to-Action Text
```

**Example:**

```
TITLE:
Future-Proof Your Career with AI CERTs®

SUBTITLE:
Become Certified. Become AI-Ready.

BODY:
AI is transforming every industry.
Upskill with globally recognized, industry-aligned AI certifications
designed for professionals who want to stay ahead.

CTA BUTTON:
Enroll Now
```

#### Step 4: Generate Images

1. Click the **"🚀 Generate Images"** button
2. Wait for the progress bar to complete
3. Images will appear in the gallery below

#### Step 5: Download Images

- **Thumbnail View**: Click "⬇️ Download" under any thumbnail
- **Full View**: Click "🔍 View Full Size" → Then "⬇️ Download"
- Files are saved as `aicerts_slide_1.png`, `aicerts_slide_2.png`, etc.

---

### For Developers

#### Project Architecture

```
ai-certs-image-generator/
│
├── app.py                 # Main Streamlit application
├── generator.py           # Image generation logic
├── prompts.py            # Brand guidelines & prompt templates
├── .env                  # Environment variables (API keys)
├── requirements.txt      # Python dependencies
│
├── assets/
│   └── default_logo.jpg  # Default brand logo
│
└── outputs/              # Generated images (auto-created)
    ├── aicerts_slide_1.png
    ├── aicerts_slide_2.png
    └── ...
```

#### Key Components

##### 1. `app.py` - Main Application

- **UI Components**: Streamlit interface with sidebar controls
- **Session State**: Manages generated images and expanded view
- **Gallery Display**: Grid layout with thumbnails and full-view
- **File Management**: Handles uploads and downloads

##### 2. `generator.py` - Image Generation Engine

```python
class AICertsImageGenerator:
    def __init__(self, api_key: str)
    def generate_and_save(
        brand_prompt: str,
        content_prompt: str,
        logo: Image.Image,
        output_path: str,
        model: str,
        aspect_ratio: str
    )
```

**Key Methods:**
- Initializes Google Gemini client
- Sends brand guidelines + content + logo to AI
- Saves generated image to specified path

##### 3. `prompts.py` - Brand Guidelines

Contains two main components:

1. **BRAND_PROMPT**: Complete AI CERTs® brand guidelines
   - Colors (Gold #CFA935, Navy #1A1A2E, etc.)
   - Typography (Montserrat, Poppins, Open Sans)
   - Spacing rules (80px padding)
   - Button styles
   - Content tone and style

2. **build_content_prompt()**: Structures user content
   - Formats the content input
   - Adds design requirements
   - Ensures brand compliance

#### Customization Guide

##### Modify Brand Colors

Edit `prompts.py`:

```python
BRAND_PROMPT = """
...
Primary:
• Gold: #YOUR_COLOR_HERE
• White: #F4F4F4
...
"""
```

##### Add New Models

Edit `app.py`:

```python
model_name = st.sidebar.selectbox(
    "Gemini Model",
    [
        "gemini-3-pro-image-preview",
        "gemini-2.5-flash-image",
        "your-new-model-here"  # Add here
    ],
)
```

##### Change Aspect Ratio

Edit `generator.py`:

```python
config=types.GenerateContentConfig(
    response_modalities=["IMAGE"],
    image_config=types.ImageConfig(
        aspect_ratio="16:9"  # Change from "1:1"
    ),
)
```

##### Custom Output Directory

Edit `app.py`:

```python
OUTPUT_DIR = "my_custom_outputs"  # Change from "outputs"
```

#### API Integration Example

```python
from generator import AICertsImageGenerator
from prompts import BRAND_PROMPT, build_content_prompt
from PIL import Image

# Initialize
api_key = "your_api_key"
generator = AICertsImageGenerator(api_key)

# Prepare content
content = """
TITLE: My Title
SUBTITLE: My Subtitle
BODY: My content here
CTA BUTTON: Click Me
"""

content_prompt = build_content_prompt(content)
logo = Image.open("path/to/logo.png")

# Generate
generator.generate_and_save(
    brand_prompt=BRAND_PROMPT,
    content_prompt=content_prompt,
    logo=logo,
    output_path="output.png",
    model="gemini-2.5-flash-image"
)
```

---

## 🎨 Brand Guidelines

### Official AI CERTs® Colors

| Color Name | Hex Code | Usage |
|------------|----------|-------|
| Gold | #CFA935 | Highlights, CTAs, Keywords |
| White | #F4F4F4 | Backgrounds, Text |
| Platinum | #E4E4E4 | Secondary backgrounds |
| Independence | #4D5060 | Body text |
| Teal | #098A7D | Accents |
| Midnight Blue | #072557 | Dark backgrounds |
| Dark Navy | #1A1A2E | Primary dark tone |
| AI Blue | #0056B3 | Tech elements |
| Pantone | #176C90 | Brand accents |

### Typography Hierarchy

- **Headlines**: Montserrat Bold/ExtraBold (48px/36px)
- **Subheadings**: Montserrat Medium
- **Body Text**: Poppins Regular/SemiBold
- **Secondary**: Open Sans

### Layout Rules

- **Canvas Size**: 1080 x 1080 pixels
- **Padding**: 80px on all sides
- **Logo Position**: Top-left (always)
- **Button Style**: Rounded or square edges, Gold (#CFA935) or White with black border

### Content Guidelines

- **Tone**: Professional, modern, educational, trust-driven
- **Keywords**: Toolkit, Upskill, Future-Proof, Certified, AI-Ready
- **CTA**: Mandatory in every post (e.g., "Enroll Now", "Book Your Seat")
- **Storytelling**: Problem → Solution format

---

## 🐛 Troubleshooting

### Common Issues

#### 1. "GOOGLE_API_KEY not found in .env"

**Solution:**
```bash
# Create .env file in project root
echo "GOOGLE_API_KEY=your_actual_key_here" > .env
```

#### 2. "No module named 'streamlit'"

**Solution:**
```bash
pip install streamlit google-genai pillow python-dotenv
```

#### 3. Images Not Generating

**Checklist:**
- ✅ Valid Google API key in `.env`
- ✅ API key has Gemini access enabled
- ✅ Content follows STRICT FORMAT
- ✅ Internet connection active
- ✅ Sufficient API quota remaining

#### 4. Logo Not Displaying

**Solution:**
```bash
# Ensure default logo exists
mkdir -p assets
# Place your logo.jpg in assets/
cp /path/to/your/logo.jpg assets/default_logo.jpg
```

#### 5. Permission Denied on `outputs/`

**Solution:**
```bash
# Create directory with proper permissions
mkdir outputs
chmod 755 outputs
```

---

## 🔧 Advanced Configuration

### Environment Variables

Create a `.env` file with:

```bash
# Required
GOOGLE_API_KEY=your_google_api_key

# Optional
OUTPUT_DIR=custom_outputs
DEFAULT_LOGO_PATH=custom_path/logo.png
```

### Streamlit Configuration

Create `.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#CFA935"
backgroundColor = "#1A1A2E"
secondaryBackgroundColor = "#4D5060"
textColor = "#F4F4F4"

[server]
maxUploadSize = 10
```

---

## 📝 Content Format Examples

### Marketing Post

```
TITLE:
AI is Reshaping Industries

SUBTITLE:
Are You Ready?

BODY:
Join 50,000+ professionals who have future-proofed their careers.
Get certified in AI skills that matter.

CTA BUTTON:
Start Learning Today
```

### Course Announcement

```
TITLE:
New AI Certification Program

SUBTITLE:
Machine Learning Essentials

BODY:
12-week intensive program.
Industry-recognized certification.
Lifetime access to course materials.

CTA BUTTON:
Reserve Your Spot
```

### Industry Insight

```
TITLE:
5 AI Trends for 2026

SUBTITLE:
Stay Ahead of the Curve

BODY:
Discover the technologies that will define the next decade.
Expert insights from AI CERTs® certified professionals.

CTA BUTTON:
Read the Full Report
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/AmazingFeature`)
3. **Commit** your changes (`git commit -m 'Add some AmazingFeature'`)
4. **Push** to the branch (`git push origin feature/AmazingFeature`)
5. **Open** a Pull Request

### Code Style

- Follow PEP 8 for Python code
- Use meaningful variable names
- Add comments for complex logic
- Update documentation for new features

---

## 📄 License

This project is proprietary software owned by AI CERTs®. Unauthorized distribution or modification is prohibited.

For licensing inquiries, contact: [info@aicerts.io](mailto:info@aicerts.io)

---

## 📧 Support

### For Users

- 📧 Email: support@aicerts.io
- 🌐 Website: [https://aicerts.io](https://aicerts.io)
- 💬 Live Demo: [https://rankifyimg.aicerts.ai/](https://rankifyimg.aicerts.ai/)

### For Developers

- 📚 Documentation: Check `/docs` folder (if available)
- 🐛 Report Issues: Use GitHub Issues
- 💡 Feature Requests: Submit via GitHub Discussions

---

## 🙏 Acknowledgments

- **Google Gemini AI**: For powerful image generation capabilities
- **Streamlit**: For the intuitive web framework
- **AI CERTs®**: For brand guidelines and design system

---

## 📊 Version History

### v1.0.0 (Current)
- ✅ Initial release
- ✅ Batch image generation (1-10 images)
- ✅ Custom logo upload
- ✅ Interactive gallery with full-view
- ✅ Brand-compliant outputs
- ✅ Multiple Gemini model support

### Roadmap

- 🔜 Export to PDF carousel
- 🔜 Bulk content upload (CSV/Excel)
- 🔜 A/B testing variations
- 🔜 Analytics dashboard
- 🔜 API endpoint for integrations

---

## ⚡ Quick Start Summary

```bash
# 1. Clone and navigate
git clone <repo-url>
cd ai-certs-image-generator

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up API key
echo "GOOGLE_API_KEY=your_key" > .env

# 4. Run the app
streamlit run app.py

# 5. Open browser to http://localhost:8501
```

---

**Made with ❤️ by AI CERTs® Team**

For more information, visit [https://aicerts.io](https://aicerts.io)