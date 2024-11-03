import os
import logging
import base64
from io import BytesIO
from typing import Optional, Tuple
from PIL import Image
from telegram import Update, File
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import NetworkError, RetryAfter
from groq import AsyncGroq
import asyncio
import json

# Configuration class for environment variables and default settings
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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
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

    async def analyze_image(self, base64_image: str) -> str:
        """Analyze image using Groq's vision model."""
        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Please describe the room's layout, colors, decor, and general energy flow."},
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

    async def generate_recommendations(self, analysis_text: str, birth_year: Optional[int]) -> str:
        """Generate structured Feng Shui recommendations based on the image and user's birth year."""
        try:
            element = self.determine_feng_shui_element(birth_year)
            json_schema = '''
            {
                "description": "string (overview of room layout and feel)",
                "feng_shui_recommendations": [
                    {
                        "aspect": "string (e.g., layout, colors, decor, energy flow)",
                        "advice": "string (specific Feng Shui recommendation)"
                    }
                ]
            }
            '''
            messages = [
                {
                    "role": "system",
                    "content": "You are a Feng Shui expert providing detailed descriptions and Feng Shui recommendations based on birth elements.\n"
                               f"The user’s Feng Shui element is {element}. Respond in JSON format using the schema: {json_schema}"
                },
                {
                    "role": "user",
                    "content": f"Based on this analysis: {analysis_text}\n\nProvide specific Feng Shui recommendations tailored to the {element} element."
                }
            ]

            response = await self.client.chat.completions.create(
                model=self.config.text_model,
                messages=messages,
                temperature=0.6,
                max_tokens=1024,
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Recommendation generation error: {e}")
            return "Failed to generate recommendations. Please try again later."

    def determine_feng_shui_element(self, birth_year: Optional[int]) -> str:
        """Determine Feng Shui element based on birth year."""
        if birth_year:
            elements = ["Wood", "Fire", "Earth", "Metal", "Water"]
            index = (birth_year - 4) % 10 // 2
            return elements[index]
        return "Unknown"

# Telegram Bot class using PTB
class FengShuiBot:
    def __init__(self, config: Config):
        self.config = config
        self.application = Application.builder().token(config.telegram_token).build()
        self.analyzer = FengShuiAnalyzer(config.groq_api_key, config)
        self.image_processor = ImageProcessor(config)
        self.setup_handlers()

    def setup_handlers(self):
        """Setup command and message handlers for the bot."""
        self.application.add_handler(CommandHandler("start", self.handle_start))
        self.application.add_handler(CommandHandler("help", self.handle_help))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_image))

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send welcome message on /start command."""
        await update.message.reply_text(
            "🏮 Welcome to the Feng Shui Analysis Bot! 🏮\n\n"
            "Send a photo of a space for personalized Feng Shui recommendations. 🌟"
        )

    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send help message on /help command."""
        await update.message.reply_text(
            "Send a photo of a room or space, along with your birth year, and I'll provide Feng Shui recommendations tailored to your element."
        )

    async def handle_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process images with retry logic and include birthday information for Feng Shui element analysis."""
        message = update.message
        processing_msg = await message.reply_text("🔄 Receiving your image...")

        # Retrieve the birth year if provided
        birth_year = None
        if context.args:
            try:
                birth_year = int(context.args[0])
            except ValueError:
                await message.reply_text("Please provide a valid birth year after the photo for personalized recommendations.")

        try:
            # Download the photo
            photo_file = await self.download_image_with_retries(message.photo[-1].file_id)
            base64_image, error = self.image_processor.process_image(photo_file)
            if error:
                await processing_msg.edit_text(f"⚠️ {error}")
                return

            await processing_msg.edit_text("🔍 Describing the space...")
            analysis_text = await self.analyzer.analyze_image(base64_image)

            await processing_msg.edit_text("✨ Generating Feng Shui recommendations...")
            recommendations = await self.analyzer.generate_recommendations(analysis_text, birth_year)

            try:
                recommendations_json = json.loads(recommendations)
                formatted_text = f"**Room Description**:\n{recommendations_json['description']}\n\n"
                formatted_text += "🌿 **Feng Shui Recommendations** 🌿\n\n"
                for rec in recommendations_json.get('feng_shui_recommendations', []):
                    aspect = rec.get('aspect', 'Aspect')
                    advice = rec.get('advice', 'Advice')
                    formatted_text += f"**{aspect.capitalize()}**:\n{advice}\n\n"
                await processing_msg.edit_text(formatted_text, parse_mode='Markdown')
            except json.JSONDecodeError:
                await processing_msg.edit_text(recommendations)

        except Exception as e:
            logger.error(f"Error processing image: {e}", exc_info=True)
            await processing_msg.edit_text("❌ Sorry, something went wrong. Please try again later.")

    async def download_image_with_retries(self, file_id: str, max_attempts: int = 3) -> BytesIO:
        """Download image with retries in case of temporary issues."""
        for attempt in range(1, max_attempts + 1):
            try:
                file: File = await self.application.bot.get_file(file_id)
                bio = BytesIO()
                await file.download_to_memory(bio)
                bio.seek(0)
                return bio
            except RetryAfter as e:
                logger.warning(f"Rate limit hit. Retrying after {e.retry_after} seconds...")
                await asyncio.sleep(e.retry_after)
            except NetworkError:
                if attempt == max_attempts:
                    raise
                logger.warning(f"Network error on attempt {attempt}. Retrying...")
                await asyncio.sleep(2 ** attempt)

    def run(self):
        """Run the bot with polling."""
        self.application.run_polling()

# Main entry point
def main():
    config = Config()
    bot = FengShuiBot(config)
    bot.run()

if __name__ == "__main__":
    main()
