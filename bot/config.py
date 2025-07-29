import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Telegram Settings
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    BOT_USERNAME = os.getenv('BOT_USERNAME')
    
    # Database Settings
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    # Game Settings
    HOUSE_EDGE = float(os.getenv('HOUSE_EDGE', 0.05))  # 5% house edge
    MIN_BET = float(os.getenv('MIN_BET', 0.01))        # Minimum bet in SOL
    MAX_BET = float(os.getenv('MAX_BET', 10.0))        # Maximum bet in SOL
    
    # Round Timing (in seconds)
    ROUND_DURATION = int(os.getenv('ROUND_DURATION', 45))
    BETTING_PHASE = int(os.getenv('BETTING_PHASE', 20))
    REVEAL_PHASE = int(os.getenv('REVEAL_PHASE', 25))
    
    # Solana Settings (for Phase 2)
    SOLANA_RPC = os.getenv('SOLANA_RPC', 'https://api.mainnet-beta.solana.com')
    ESCROW_PRIVATE_KEY = os.getenv('ESCROW_PRIVATE_KEY')
    HOUSE_WALLET = os.getenv('HOUSE_WALLET')
    
    # Server Settings
    PORT = int(os.getenv('PORT', 3000))
    WS_PORT = int(os.getenv('WS_PORT', 3001))
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    
    # Debug Mode
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
    
    @classmethod
    def validate_config(cls):
        """Validate that required configuration is present"""
        required_vars = ['BOT_TOKEN', 'DATABASE_URL']
        missing_vars = [var for var in required_vars if not getattr(cls, var)]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return True

# Game Constants
class GameConstants:
    BET_TYPES = {
        'PUMP': '📈 PUMP',
        'DUMP': '📉 DUMP'
    }
    
    ROUND_STATUSES = {
        'WAITING': 'waiting',
        'BETTING': 'betting', 
        'REVEALING': 'revealing',
        'COMPLETED': 'completed'
    }
    
    EMOJIS = {
        'PUMP': '📈',
        'DUMP': '📉',
        'MONEY': '💰',
        'FIRE': '🔥',
        'ROCKET': '🚀',
        'CHART': '📊',
        'TIMER': '⏱️',
        'WINNER': '🏆',
        'LOSER': '😢'
    }

# Messages Templates
class Messages:
    WELCOME = """
🎰 **Welcome to Pump or Dump!**

The most exciting crypto betting game on Telegram!

**How to Play:**
📈 Choose PUMP if you think the chart will go UP
📉 Choose DUMP if you think the chart will go DOWN
⏱️ Each round lasts 45 seconds
💰 Winners split the pot (minus 5% house edge)

**Commands:**
/play - Join the current round
/stats - View your statistics  
/balance - Check your balance
/help - Show this message

🚀 **Ready to get started? Use /play to join the next round!**
    """
    
    ROUND_STARTING = """
🔥 **NEW ROUND STARTING!** 🔥

Round #{round_number}
⏱️ Betting Phase: {betting_time} seconds

Choose your side:
📈 PUMP - Chart goes UP
📉 DUMP - Chart goes DOWN

💰 Current pot: {total_pot} SOL
👥 Players: {player_count}

**Place your bet now!**
    """
    
    BETTING_CLOSED = """
⏰ **BETTING CLOSED!**

Round #{round_number}
📊 **Final Stats:**
💰 Total Pot: {total_pot} SOL
📈 PUMP Bets: {pump_pot} SOL ({pump_percentage}%)
📉 DUMP Bets: {dump_pot} SOL ({dump_percentage}%)
👥 Total Players: {player_count}

🎲 **Revealing result in {reveal_time} seconds...**
The chart is moving... 📈📉
    """
    
    ROUND_RESULT = """
🏆 **ROUND #{round_number} RESULT** 🏆

Result: {result_emoji} **{result}**

📊 **Pot Distribution:**
💰 Total Pot: {total_pot} SOL
🏠 House Edge (5%): {house_cut} SOL
🎉 Winners Pool: {winners_pool} SOL
📈 Multiplier: {multiplier}x

{winner_message}

⏱️ Next round starts in 5 seconds...
    """