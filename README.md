# PeaceScape AI 🏮

PeaceScape AI is a Telegram bot designed to provide Feng Shui insights and recommendations based on room images. Users can send a photo of their space, along with their birth year, and receive a personalized analysis that includes a description of the space's layout, colors, decor, and energy flow. PeaceScape AI offers suggestions tailored to the user’s Feng Shui element, helping to harmonize their environment.

## Features

- **Image-Based Feng Shui Analysis**: Uses AI to analyze a photo of a room, identifying elements related to Feng Shui principles.
- **Personalized Recommendations**: Tailors suggestions based on the user’s Feng Shui element, calculated from their birth year.
- **Detailed Room Description**: Provides an initial analysis of the room's layout, colors, and decor before giving recommendations.
- **User-Friendly Output**: Organizes responses with clear sections for easy reading.

## Demo

Here’s how you can interact with PeaceScape AI:

1. **Start the bot**: `/start`
2. **Help**: `/help` - Displays guidance on using the bot.
3. **Send a Room Photo**: 
   - Take or upload a photo of a room.
   - Optionally, add your birth year to receive Feng Shui suggestions tailored to your element (e.g., 1990).

The bot will return:
- A **description** of the room's layout and general energy flow.
- **Feng Shui recommendations** based on your personal Feng Shui element.

## Feng Shui Element Calculation

PeaceScape AI calculates your Feng Shui element based on your birth year. Feng Shui elements include Wood, Fire, Earth, Metal, and Water, and are derived from the last digit of the birth year to personalize each recommendation.

## Installation

To set up PeaceScape AI, follow these steps:

### Prerequisites

- Python 3.8 or higher
- [Telegram API Token](https://core.telegram.org/bots#botfather)
- [Groq API Key](https://groq.com/) for vision analysis

### Install Dependencies

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/peacescape-ai.git
   cd peacescape-ai
   ```

2. Install required packages:

   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables for your API keys:

   ```bash
   export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
   export GROQ_API_KEY="your-groq-api-key"
   ```

### Run the Bot

Run the bot with:

```bash
python peacescape_bot.py
```

The bot will start and begin listening for messages.

## Project Structure

```plaintext
PeaceScape AI/
├── peacescape_bot.py          # Main bot code
├── README.md                  # Project README
├── requirements.txt           # Dependencies for the bot
└── .env                       # Environment variables for API keys (optional)
```

## Usage Instructions

1. **Send a photo** of a room to the bot in Telegram.
2. **Optionally include** your birth year for personalized recommendations.
3. PeaceScape AI will:
   - Describe your space’s layout and energy flow.
   - Provide Feng Shui recommendations.

## Example Interaction

User uploads a photo of a living room and provides the birth year `1987`:

**Bot Response:**

```
🌿 **PeaceScape AI - Feng Shui Analysis** 🌿

**Room Description**:
The room has a spacious layout with neutral colors and minimal decor, offering an open and calming energy flow.

🌿 **Feng Shui Recommendations** 🌿

- **Layout**: Arrange furniture to create balanced spaces.
- **Colors**: Add Earth tones for stability.
- **Decor**: Place plants near windows to enhance Wood element.
- **Energy Flow**: Keep pathways clear to maintain positive energy flow.

Your Feng Shui Element: Fire 🔥 - Strengthen this element with red accents and dynamic patterns.
```

## Contributing

We welcome contributions! Feel free to fork the repository, make improvements, and submit a pull request. If you encounter any issues, please open an issue for discussion.

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Contact

**Project Maintainer**: [Your Name](https://github.com/yourusername)

**Project Repository**: [PeaceScape AI on GitHub](https://github.com/yourusername/peacescape-ai)

---

### Notes

- Customize the example response based on what PeaceScape AI returns.
- Add links to the Telegram BotFather and Groq API sign-up pages if you want users to get API keys.
- Replace `"yourusername"` with your GitHub username. 

This README provides clear instructions, features, and usage examples for users and contributors alike. Let me know if there’s anything else you’d like to add!
