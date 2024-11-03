import os
import logging
import base64
from io import BytesIO
from datetime import datetime
from typing import Optional, Tuple, Dict
from PIL import Image
from telegram import Update, File
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.error import NetworkError, RetryAfter
from groq import AsyncGroq
import asyncio
import json

# Define states for the conversation
BIRTH_YEAR, BIRTH_MONTH, BIRTH_DAY, GENDER, ROOM_DIRECTION, PHOTO = range(6)

# System Prompt Configuration
SYSTEM_PROMPT = """You are a highly knowledgeable Feng Shui Master with expertise in both Traditional and Modern Feng Shui practices.
Your role is to analyze spaces based on provided images and the user's personal energy, calculated from:
- Birth year (Kua number and element)
- Birth month and day (influences personal chi)
- Gender (affects energy calculations)
- Compass direction of their room.

For each analysis, provide recommendations structured as:
{
    "personal_energy": {
        "element": string,
        "kua_number": integer,
        "lucky_directions": [string],
        "challenging_directions": [string]
    },
    "space_analysis": {
        "current_energy_flow": string,
        "problem_areas": [string],
        "positive_features": [string]
    },
    "recommendations": [
        {
            "category": string,
            "issue": string,
            "solution": string,
            "priority": integer
        }
    ]
}"""

# Configuration for environment variables and default settings
class Config:
    def __init__(self):
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.max_image_size_mb = 4
        self.max_image_dimension = 2048
        self.jpeg_quality = 85
        self.vision_model = "llama-3.2-90b-vision-preview"
        self.text_model = "llama-3.2-3b-preview"

# Enhanced logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Image Processor for resizing and encoding images
class ImageProcessor:
    def __init__(self, config: Config):
        self.config = config

    def process_image(self, photo_file: BytesIO) -> Tuple[Optional[str], Optional[str]]:
        """Process and validate images."""
        try:
            photo_file.seek(0, 2)
            size_mb = photo_file.tell() / (1024 * 1024)
            if size_mb > self.config.max_image_size_mb:
                return None, f"Image size ({size_mb:.1f}MB) exceeds {self.config.max_image_size_mb}MB limit."
            photo_file.seek(0)
            with Image.open(photo_file) as img:
                if img.format.lower() not in ['jpeg', 'png']:
                    return None, f"Unsupported format: {img.format}. Please use JPEG or PNG."
                if max(img.size) > self.config.max_image_dimension:
                    ratio = self.config.max_image_dimension / max(img.size)
                    new_size = tuple(int(dim * ratio) for dim in img.size)
                    img = img.resize(new_size, Image.LANCZOS)
                buffer = BytesIO()
                img.convert('RGB').save(buffer, format='JPEG', quality=self.config.jpeg_quality)
                return base64.b64encode(buffer.getvalue()).decode('utf-8'), None
        except Exception as e:
            logger.error(f"Image processing error: {e}")
            return None, "Failed to process image. Please try another photo."

# Feng Shui Analyzer using Groq's API
class FengShuiAnalyzer:
    def __init__(self, api_key: str, config: Config):
        self.client = AsyncGroq(api_key=api_key)
        self.config = config

    async def analyze_image(self, base64_image: str, personal_energy: Dict[str, any]) -> str:
        """Analyze image using Groq's vision model."""
        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Analyze based on user's personal energy: {personal_energy}"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ]
            response = await self.client.chat.completions.create(
                model=self.config.vision_model,
                messages=messages,
                temperature=0.7,
                max_tokens=1024
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Vision analysis error: {e}")
            return "Vision analysis failed. Please try again later."

    async def generate_recommendations(self, analysis_text: str, personal_energy: Dict[str, any]) -> dict:
        """Generate structured Feng Shui recommendations using text model."""
        try:
            messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": f"Based on this analysis: {analysis_text}\n\n"
                               "Provide specific Feng Shui recommendations in JSON format tailored to the user's energy. "
                               "Ensure the output follows JSON structure."
                }
            ]
            response = await self.client.chat.completions.create(
                model=self.config.text_model,
                messages=messages,
                temperature=0.6,
                max_tokens=1024,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response.")
            return {"error": "Failed to generate recommendations in JSON format."}
        except Exception as e:
            logger.error(f"Recommendation generation error: {e}")
            return {"error": "Failed to generate recommendations. Please try again later."}

    def calculate_kua_number(self, year: int, gender: str) -> int:
        """Calculate Kua number based on birth year and gender."""
        last_digit = sum(int(d) for d in str(year)) % 9
        if gender.upper() == 'M':
            return (10 - last_digit) if last_digit != 0 else 1
        return (last_digit + 5) if last_digit != 0 else 8

# ConversationHandler steps for sequential input collection
class FengShuiBot:
    def __init__(self, config: Config):
        self.config = config
        self.application = Application.builder().token(config.telegram_token).build()
        self.analyzer = FengShuiAnalyzer(config.groq_api_key, config)
        self.image_processor = ImageProcessor(config)
        self.setup_handlers()

    def setup_handlers(self):
        """Setup command and message handlers for the bot."""
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                BIRTH_YEAR: [MessageHandler(filters.TEXT, self.collect_birth_year)],
                BIRTH_MONTH: [MessageHandler(filters.TEXT, self.collect_birth_month)],
                BIRTH_DAY: [MessageHandler(filters.TEXT, self.collect_birth_day)],
                GENDER: [MessageHandler(filters.TEXT, self.collect_gender)],
                ROOM_DIRECTION: [MessageHandler(filters.TEXT, self.collect_room_direction)],
                PHOTO: [MessageHandler(filters.PHOTO, self.collect_photo)]
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        )
        self.application.add_handler(conv_handler)
        self.application.add_handler(CommandHandler("help", self.handle_help))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Initiate the user data collection by prompting for the birth year."""
        await update.message.reply_text("🏮 Welcome to PeaceScape AI! 🏮\n\nPlease enter your birth year (YYYY):")
        return BIRTH_YEAR

    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send help message on /help command."""
        await update.message.reply_text(
            "To get started with PeaceScape AI, enter the details step-by-step as prompted."
        )

    async def collect_birth_year(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Collect and validate birth year."""
        try:
            birth_year = int(update.message.text)
            if 1900 <= birth_year <= datetime.now().year:
                context.user_data['birth_year'] = birth_year
                await update.message.reply_text("Enter your birth month (1-12):")
                return BIRTH_MONTH
            else:
                await update.message.reply_text("Please enter a valid birth year (e.g., 1990).")
                return BIRTH_YEAR
        except ValueError:
            await update.message.reply_text("Please enter a valid numeric birth year.")
            return BIRTH_YEAR

    async def collect_birth_month(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Collect and validate birth month."""
        try:
            birth_month = int(update.message.text)
            if 1 <= birth_month <= 12:
                context.user_data['birth_month'] = birth_month
                await update.message.reply_text("Enter your birth day (1-31):")
                return BIRTH_DAY
            else:
                await update.message.reply_text("Please enter a valid month (1-12).")
                return BIRTH_MONTH
        except ValueError:
            await update.message.reply_text("Please enter a valid numeric month.")
            return BIRTH_MONTH

    async def collect_birth_day(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Collect and validate birth day."""
        try:
            birth_day = int(update.message.text)
            if 1 <= birth_day <= 31:
                context.user_data['birth_day'] = birth_day
                await update.message.reply_text("Enter your gender (M/F):")
                return GENDER
            else:
                await update.message.reply_text("Please enter a valid day (1-31).")
                return BIRTH_DAY
        except ValueError:
            await update.message.reply_text("Please enter a valid numeric day.")
            return BIRTH_DAY

    async def collect_gender(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Collect and validate gender."""
        gender = update.message.text.strip().upper()
        if gender in ['M', 'F']:
            context.user_data['gender'] = gender
            await update.message.reply_text("What direction does your room face? (N/S/E/W/NE/NW/SE/SW):")
            return ROOM_DIRECTION
        else:
            await update.message.reply_text("Please enter 'M' for male or 'F' for female.")
            return GENDER

    async def collect_room_direction(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Collect and validate room direction."""
        direction = update.message.text.strip().upper()
        if direction in ['N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW']:
            context.user_data['room_direction'] = direction
            await update.message.reply_text("Please upload a photo of your space.")
            return PHOTO
        else:
            await update.message.reply_text("Please enter a valid compass direction (N/S/E/W/NE/NW/SE/SW).")
            return ROOM_DIRECTION

    async def collect_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Process photo and trigger Feng Shui analysis."""
        message = update.message
        photo_file = await self.download_image_with_retries(update.message.photo[-1].file_id)
        base64_image, error = self.image_processor.process_image(photo_file)
        if error:
            await message.reply_text(f"⚠️ {error}")
            return PHOTO

        # Generate Feng Shui analysis with all user data collected
        await message.reply_text("🔄 Generating your personalized Feng Shui analysis...")
        user_data = context.user_data
        kua_number = self.analyzer.calculate_kua_number(user_data['birth_year'], user_data['gender'])
        personal_energy = {
            "element": "To be calculated",  # Placeholder
            "kua_number": kua_number,
            "lucky_directions": ["N", "E"],  # Placeholder
            "challenging_directions": ["SW", "NW"]
        }

        # Analyze image and get recommendations
        analysis_text = await self.analyzer.analyze_image(base64_image, personal_energy)
        recommendations = await self.analyzer.generate_recommendations(analysis_text, personal_energy)

        # Ensure recommendations are a dictionary for parsing
        if isinstance(recommendations, dict) and "error" not in recommendations:
            response = format_feng_shui_response(recommendations)
            await message.reply_text(response, parse_mode='Markdown')
        else:
            await message.reply_text(recommendations.get("error", "An error occurred."))
        return ConversationHandler.END

    async def download_image_with_retries(self, file_id: str, max_attempts: int = 3) -> BytesIO:
        for attempt in range(1, max_attempts + 1):
            try:
                file: File = await self.application.bot.get_file(file_id)
                bio = BytesIO()
                await file.download_to_memory(bio)
                bio.seek(0)
                return bio
            except NetworkError:
                if attempt == max_attempts:
                    raise
                await asyncio.sleep(2 ** attempt)

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("Operation cancelled.")
        return ConversationHandler.END

# Helper function to format Feng Shui response
def format_feng_shui_response(recommendations_json: dict) -> str:
    """Format the Feng Shui recommendations for user-friendly output."""
    personal_energy = recommendations_json.get('personal_energy', {})
    space_analysis = recommendations_json.get('space_analysis', {})
    recommendations = recommendations_json.get('recommendations', [])

    # Format recommendations into readable text
    recommendations_text = "\n".join(
        f"- {rec.get('category', 'General')}: {rec.get('issue', 'Issue')} - {rec.get('solution', 'Solution')} (Priority: {rec.get('priority', 'Medium')})"
        for rec in recommendations
    )

    return (
        "🔮 **Your Personalized Feng Shui Analysis**\n\n"
        "**Personal Energy Profile**\n"
        f"Element: {personal_energy.get('element', 'Unknown')}\n"
        f"Kua Number: {personal_energy.get('kua_number', 'N/A')}\n"
        f"Lucky Directions: {', '.join(personal_energy.get('lucky_directions', []))}\n\n"
        "**Room Analysis**\n"
        f"{space_analysis.get('current_energy_flow', 'No data')}\n\n"
        "**Recommendations**\n"
        f"{recommendations_text}"
    )

# Main entry point to run the bot
def main():
    config = Config()
    bot = FengShuiBot(config)
    bot.application.run_polling()

if __name__ == "__main__":
    main()
