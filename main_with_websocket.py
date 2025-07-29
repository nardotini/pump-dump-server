#!/usr/bin/env python3
"""
Ultimate bot with WebSocket integration and Telegram Web App for real-time chart updates
"""

import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher, 
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from dotenv import load_dotenv
from decimal import Decimal
import time

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Import after path setup
try:
    from bot.config import Config
    from bot.services.database import db
    from backend.websocket_server import websocket_server
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

# Initialize bot
bot = Bot(token=Config.BOT_TOKEN, parse_mode='Markdown')
dp = Dispatcher()

# 🚀 TELEGRAM WEB APP URL - Replace with your GitHub Pages URL
CHART_WEB_APP_URL = "https://nardotini.github.io/pump-dump-chart"

# Game state
current_round = {
    'id': 0,
    'number': 0,
    'status': 'waiting',
    'bets': {},
    'total_pot': 0.0,
    'pump_pot': 0.0,
    'dump_pot': 0.0,
    'betting_users': set(),
    'all_users': set(),
    'active_players': set(),
    'start_time': 0,
    'betting_end_time': 0
}

def get_main_keyboard() -> InlineKeyboardMarkup:
    """Get main keyboard with Telegram Web App integration"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📊 LIVE CHART 🎰", 
                web_app=WebAppInfo(url=CHART_WEB_APP_URL)
            )
        ],
        [
            InlineKeyboardButton(text="🎮 Play Now", callback_data="play"),
            InlineKeyboardButton(text="💰 Balance", callback_data="balance")
        ],
        [
            InlineKeyboardButton(text="📊 My Stats", callback_data="stats"),
            InlineKeyboardButton(text="❓ Help", callback_data="help")
        ]
    ])

def get_betting_keyboard() -> InlineKeyboardMarkup:
    """Get betting keyboard with integrated live chart"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📈 WATCH LIVE CHART 🎯", 
                web_app=WebAppInfo(url=CHART_WEB_APP_URL)
            )
        ],
        [
            InlineKeyboardButton(text="📈 PUMP 0.1", callback_data="bet_PUMP_0.1"),
            InlineKeyboardButton(text="📉 DUMP 0.1", callback_data="bet_DUMP_0.1")
        ],
        [
            InlineKeyboardButton(text="📈 PUMP 0.5", callback_data="bet_PUMP_0.5"),
            InlineKeyboardButton(text="📉 DUMP 0.5", callback_data="bet_DUMP_0.5")
        ],
        [
            InlineKeyboardButton(text="🔄 Refresh", callback_data="play"),
            InlineKeyboardButton(text="🏠 Menu", callback_data="main_menu")
        ]
    ])

def get_time_remaining():
    """Get time remaining in current phase"""
    if current_round['status'] == 'betting':
        remaining = int(current_round['betting_end_time'] - time.time())
        return max(0, remaining)
    return 0

async def fix_user_balance(telegram_id):
    """Fix negative balance by resetting to 1 SOL"""
    try:
        async with db.pool.acquire() as conn:
            user = await conn.fetchrow("SELECT balance FROM users WHERE telegram_id = $1", telegram_id)
            if user and float(user['balance']) < 0:
                await conn.execute("UPDATE users SET balance = 1.0 WHERE telegram_id = $1", telegram_id)
                print(f"🔧 Fixed negative balance for user {telegram_id}")
                return True
    except Exception as e:
        logger.error(f"Balance fix error: {e}")
    return False

@dp.message(CommandStart())
async def start_command(message: Message):
    """Enhanced start command with Telegram Web App"""
    current_round['all_users'].add(message.from_user.id)
    current_round['active_players'].add(message.from_user.id)
    
    user = await db.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    
    if float(user['balance']) < 0:
        await fix_user_balance(message.from_user.id)
        user = await db.get_or_create_user(message.from_user.id)
    
    welcome_text = f"""
🎰 **Welcome to Pump or Dump!**

Hello {message.from_user.first_name}! 

**🆕 LIVE CHART IN TELEGRAM!**
📊 Tap "LIVE CHART" to watch real-time action
📱 Everything inside Telegram - no browser needed!

**How to Play:**
📈 Choose PUMP if chart goes UP
📉 Choose DUMP if chart goes DOWN
⏱️ Each round: 20s betting + 15s reveal
💰 Winners split the pot (5% house edge)

**Your Balance:** {float(user['balance']):.3f} SOL

🚀 **Ready to gamble?**
    """
    
    if current_round['status'] == 'betting':
        time_left = get_time_remaining()
        welcome_text += f"\n\n🔥 **ROUND #{current_round['number']} LIVE!**\n"
        welcome_text += f"⏰ **{time_left}s left to bet!**\n"
        welcome_text += f"💰 Pot: {current_round['total_pot']:.3f} SOL"
    elif current_round['status'] == 'revealing':
        welcome_text += f"\n\n🎲 **ROUND #{current_round['number']} REVEALING...**\n"
        welcome_text += f"💰 Total pot: {current_round['total_pot']:.3f} SOL"
    elif current_round['status'] == 'waiting':
        welcome_text += f"\n\n⏳ **Next round starting soon!**"
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

@dp.message(Command("play"))
async def play_command(message: Message):
    """Enhanced play command with Web App integration"""
    current_round['all_users'].add(message.from_user.id)
    current_round['active_players'].add(message.from_user.id)
    
    user = await db.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    
    if float(user['balance']) < 0:
        await fix_user_balance(message.from_user.id)
        user = await db.get_or_create_user(message.from_user.id)
    
    if current_round['status'] == 'waiting':
        await message.answer("⏳ **Next round starting soon...**\n\nGet ready!", reply_markup=get_main_keyboard())
        return
    
    if current_round['status'] == 'revealing':
        await message.answer("🎲 **Round in progress!**\n\nRevealing result... Next round coming up!", reply_markup=get_main_keyboard())
        return
    
    if message.from_user.id in current_round['bets']:
        bet = current_round['bets'][message.from_user.id]
        time_left = get_time_remaining()
        
        already_bet_text = f"""
✅ **You're in this round!**

🎯 **Round #{current_round['number']}**
⏰ **{time_left}s until betting closes**

**Your Bet:** {'📈 PUMP' if bet['type'] == 'PUMP' else '📉 DUMP'} {bet['amount']} SOL
**Your Balance:** {float(user['balance']):.3f} SOL

**Live Pot Updates:**
💰 Total: {current_round['total_pot']:.3f} SOL
📈 PUMP: {current_round['pump_pot']:.3f} SOL
📉 DUMP: {current_round['dump_pot']:.3f} SOL
👥 Players: {len(current_round['bets'])}

📊 **Watch the Live Chart for real-time action!**
        """
        await message.answer(already_bet_text, reply_markup=get_main_keyboard())
        return
    
    time_left = get_time_remaining()
    
    betting_text = f"""
🔥 **ROUND #{current_round['number']} - BETTING OPEN**

⏰ **{time_left} seconds remaining!**

**Live Pot:**
💰 Total: {current_round['total_pot']:.3f} SOL
📈 PUMP: {current_round['pump_pot']:.3f} SOL
📉 DUMP: {current_round['dump_pot']:.3f} SOL
👥 Players: {len(current_round['bets'])}

**Your Balance:** {float(user['balance']):.3f} SOL

**Place your bet now!**

📊 **Tap "WATCH LIVE CHART" for real-time action!**
    """
    
    await message.answer(betting_text, reply_markup=get_betting_keyboard())

@dp.callback_query(F.data.startswith("bet_"))
async def bet_callback(callback):
    """Handle bet placement with WebSocket updates"""
    if current_round['status'] != 'betting':
        await callback.answer("❌ Betting is closed!", show_alert=True)
        return
    
    time_left = get_time_remaining()
    if time_left <= 0:
        await callback.answer("❌ Time's up! Betting closed!", show_alert=True)
        return
    
    if callback.from_user.id in current_round['bets']:
        await callback.answer("❌ You already placed a bet this round!", show_alert=True)
        return
    
    parts = callback.data.split("_")
    bet_type = parts[1]
    amount = float(parts[2])
    
    user = await db.get_or_create_user(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name
    )
    
    if float(user['balance']) < 0:
        await fix_user_balance(callback.from_user.id)
        user = await db.get_or_create_user(callback.from_user.id)
    
    balance = float(user['balance'])
    
    if balance < amount:
        await callback.answer(f"❌ Need {amount} SOL! You have {balance:.3f} SOL", show_alert=True)
        return
    
    try:
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE users SET balance = balance - $1, total_wagered = total_wagered + $1 WHERE telegram_id = $2",
                    Decimal(str(amount)), callback.from_user.id
                )
                
                current_round['bets'][callback.from_user.id] = {
                    'type': bet_type,
                    'amount': amount,
                    'user': callback.from_user.first_name,
                    'chat_id': callback.message.chat.id
                }
                
                current_round['betting_users'].add(callback.from_user.id)
                current_round['active_players'].add(callback.from_user.id)
                
                current_round['total_pot'] += amount
                if bet_type == 'PUMP':
                    current_round['pump_pot'] += amount
                else:
                    current_round['dump_pot'] += amount
        
        # 🚀 UPDATE WEBSOCKET WITH NEW BET
        await websocket_server.update_bet_placed(
            bet_type=bet_type,
            amount=amount,
            pump_pot=current_round['pump_pot'],
            dump_pot=current_round['dump_pot'],
            player_count=len(current_round['bets'])
        )
        
        await callback.answer(f"✅ {amount} SOL on {bet_type}! Good luck!")
        
        time_left = get_time_remaining()
        
        success_text = f"""
✅ **Bet Placed Successfully!**

🎯 **Round #{current_round['number']}**
⏰ **{time_left}s left in betting phase**

**Your Bet:** {'📈 PUMP' if bet_type == 'PUMP' else '📉 DUMP'} {amount} SOL
**New Balance:** {balance - amount:.3f} SOL

**Updated Live Pot:**
💰 Total: {current_round['total_pot']:.3f} SOL
📈 PUMP: {current_round['pump_pot']:.3f} SOL
📉 DUMP: {current_round['dump_pot']:.3f} SOL
👥 Players: {len(current_round['bets'])}

🍀 **You're in! Watch the Live Chart!**
        """
        
        await callback.message.edit_text(success_text, reply_markup=get_main_keyboard())
        
    except Exception as e:
        logger.error(f"Bet placement error: {e}")
        await callback.answer("❌ Database error! Try again.", show_alert=True)

@dp.callback_query(F.data == "balance")
async def balance_callback(callback):
    """Show balance with Web App integration"""
    user = await db.get_or_create_user(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name
    )
    
    if float(user['balance']) < 0:
        await fix_user_balance(callback.from_user.id)
        user = await db.get_or_create_user(callback.from_user.id)
    
    win_rate = (user['wins'] / max(user['games_played'], 1) * 100)
    profit = float(user['total_won']) - float(user['total_wagered'])
    
    balance_text = f"""
💰 **Your Account**

**Balance:** {float(user['balance']):.6f} SOL
**Net Profit:** {profit:+.6f} SOL

**Statistics:**
🎮 Games Played: {user['games_played']}
🏆 Wins: {user['wins']}
😢 Losses: {user['losses']}
📊 Win Rate: {win_rate:.1f}%

**Lifetime Stats:**
💸 Total Wagered: {float(user['total_wagered']):.6f} SOL
💰 Total Won: {float(user['total_won']):.6f} SOL

📊 **Check the Live Chart for real-time action!**
    """
    
    try:
        await callback.message.edit_text(balance_text, reply_markup=get_main_keyboard())
    except Exception:
        await callback.answer()
        await bot.send_message(callback.from_user.id, balance_text, reply_markup=get_main_keyboard())

@dp.callback_query(F.data == "stats")
async def stats_callback(callback):
    """Show detailed stats"""
    try:
        await balance_callback(callback)
    except Exception:
        await callback.answer("📊 Stats updated!")

@dp.callback_query(F.data == "play")
async def play_callback(callback):
    """Handle play button with Web App"""
    await play_command(callback.message)
    await callback.answer()

@dp.callback_query(F.data == "main_menu")
async def main_menu_callback(callback):
    """Handle main menu with Web App"""
    await start_command(callback.message)
    await callback.answer()

@dp.callback_query(F.data == "help")
async def help_callback(callback):
    """Show help with Web App integration"""
    help_text = """
🎰 **Pump or Dump Guide**

**🆕 TELEGRAM WEB APP:**
📊 Tap "LIVE CHART" for real-time action
📱 Everything works inside Telegram!

**How to Play:**
📈 PUMP = Chart goes UP
📉 DUMP = Chart goes DOWN
🎯 Guess correctly to win!

**Round Structure:**
⏰ 20 seconds - Betting phase
🎲 15 seconds - Revealing result
💰 Instant payouts to winners

**Payouts:**
• Winners split the pot
• House takes 5% fee
• Higher multiplier = fewer people on winning side

**Features:**
🔔 Automatic notifications
⏰ Live countdown timers
📊 Detailed statistics
💻 Live chart in Telegram!

**Tips:**
• Start with 0.1 SOL bets
• Watch the live chart
• You get automatic notifications
• Balance updates instantly

**Commands:**
/start - Main menu
/play - Join current round

🚀 **Good luck gambling!**
    """
    
    try:
        await callback.message.edit_text(help_text, reply_markup=get_main_keyboard())
    except Exception:
        await callback.answer()
        await bot.send_message(callback.from_user.id, help_text, reply_markup=get_main_keyboard())
    
    await callback.answer()

async def notify_with_betting_interface(user_ids, message_text):
    """Send message with Web App betting interface"""
    for user_id in user_ids:
        try:
            if current_round['status'] == 'betting' and user_id in current_round['active_players']:
                user = await db.get_or_create_user(user_id)
                if user:
                    time_left = get_time_remaining()
                    
                    betting_text = f"""
{message_text}

🔥 **ROUND #{current_round['number']} - BETTING OPEN**

⏰ **{time_left} seconds remaining!**

**Live Pot:**
💰 Total: {current_round['total_pot']:.3f} SOL
📈 PUMP: {current_round['pump_pot']:.3f} SOL
📉 DUMP: {current_round['dump_pot']:.3f} SOL

**Your Balance:** {float(user['balance']):.3f} SOL

📊 **Tap "WATCH LIVE CHART" for real-time action!**
                    """
                    
                    await bot.send_message(user_id, betting_text, reply_markup=get_betting_keyboard(), parse_mode='Markdown')
                else:
                    await bot.send_message(user_id, message_text, reply_markup=get_main_keyboard(), parse_mode='Markdown')
            else:
                await bot.send_message(user_id, message_text, reply_markup=get_main_keyboard(), parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {e}")

async def notify_betting_users(message_text, keyboard=None):
    """Send message to users who bet this round"""
    for user_id in current_round['betting_users'].copy():
        try:
            if keyboard:
                await bot.send_message(user_id, message_text, reply_markup=keyboard, parse_mode='Markdown')
            else:
                await bot.send_message(user_id, message_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to notify betting user {user_id}: {e}")

async def send_startup_notification():
    """Enhanced startup notification with Web App"""
    try:
        async with db.pool.acquire() as conn:
            users = await conn.fetch("SELECT telegram_id FROM users")
            
        startup_text = """
🚀 **Pump or Dump Bot is BACK ONLINE!**

The gambling fun continues! 🎰

**🆕 NOW WITH TELEGRAM WEB APP!**
📊 Live chart directly in Telegram
📱 No browser needed - everything inside the app!
🎯 Real-time betting action
🎲 Dramatic reveal animations

**Ready to play?** New rounds start automatically!

📊 **Tap "LIVE CHART" to experience the future of Telegram gambling!**
        """
        
        for user_row in users:
            user_id = user_row['telegram_id']
            current_round['all_users'].add(user_id)
            current_round['active_players'].add(user_id)
            try:
                await bot.send_message(user_id, startup_text, reply_markup=get_main_keyboard(), parse_mode='Markdown')
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Failed to notify user {user_id} of startup: {e}")
        
        print(f"📢 Sent Web App startup notifications to {len(users)} users")
        
    except Exception as e:
        logger.error(f"Startup notification error: {e}")

async def send_countdown_updates():
    """Send countdown updates during betting phase"""
    countdown_times = [10, 5]
    
    for countdown in countdown_times:
        while get_time_remaining() > countdown:
            await asyncio.sleep(1)
            if current_round['status'] != 'betting':
                return
        
        if current_round['status'] == 'betting' and current_round['bets']:
            pump_pct = (current_round['pump_pot']/max(current_round['total_pot'],0.001)*100)
            dump_pct = (current_round['dump_pot']/max(current_round['total_pot'],0.001)*100)
            
            countdown_text = f"""
⏰ **{countdown} SECONDS LEFT!**

**Round #{current_round['number']} Status:**
💰 Total Pot: {current_round['total_pot']:.3f} SOL
📈 PUMP: {current_round['pump_pot']:.3f} SOL ({pump_pct:.1f}%)
📉 DUMP: {current_round['dump_pot']:.3f} SOL ({dump_pct:.1f}%)
👥 Players: {len(current_round['bets'])}

📊 **Watch the Live Chart for dramatic action!**
{'🔥 **Last chance to bet!**' if countdown == 5 else '⚡ **Hurry up!**'}
            """
            
            await notify_betting_users(countdown_text)

async def game_loop():
    """Ultimate game loop with WebSocket and Web App integration"""
    await send_startup_notification()
    await asyncio.sleep(5)
    
    round_number = 1
    
    while True:
        try:
            print(f"\n🎲 Starting Round #{round_number}")
            
            start_time = time.time()
            current_round.update({
                'id': round_number,
                'number': round_number,
                'status': 'betting',
                'bets': {},
                'total_pot': 0.0,
                'pump_pot': 0.0,
                'dump_pot': 0.0,
                'betting_users': set(),
                'start_time': start_time,
                'betting_end_time': start_time + 20
            })
            
            # 🚀 NOTIFY WEBSOCKET OF NEW ROUND
            await websocket_server.update_round_started(round_number)
            
            round_start_message = f"🔥 **NEW ROUND #{round_number} STARTED!**\n\n⏱️ **20 seconds to place bets!**\n📈 Choose PUMP or DUMP 📉\n\n📊 **Watch the Live Chart!**"
            
            await notify_with_betting_interface(current_round['active_players'], round_start_message)
            
            print(f"🎰 Round #{round_number} - Betting phase (20s)")
            
            countdown_task = asyncio.create_task(send_countdown_updates())
            
            # Timer updates for WebSocket
            async def update_timer_loop():
                """Update WebSocket timer every second"""
                while current_round['status'] == 'betting':
                    time_left = get_time_remaining()
                    await websocket_server.update_timer(time_left)
                    await asyncio.sleep(1)
            
            timer_task = asyncio.create_task(update_timer_loop())
            
            await asyncio.sleep(20)
            
            current_round['status'] = 'revealing'
            countdown_task.cancel()
            timer_task.cancel()
            
            # 🚀 NOTIFY WEBSOCKET BETTING CLOSED
            await websocket_server.update_betting_closed(
                round_number=round_number,
                pump_pot=current_round['pump_pot'],
                dump_pot=current_round['dump_pot'],
                player_count=len(current_round['bets'])
            )
            
            if current_round['bets']:
                pump_pct = (current_round['pump_pot']/max(current_round['total_pot'],0.001)*100)
                dump_pct = (current_round['dump_pot']/max(current_round['total_pot'],0.001)*100)
                
                await notify_betting_users(
                    f"⏰ **BETTING CLOSED!**\n\n"
                    f"**Round #{round_number} Final Stats:**\n"
                    f"💰 Total Pot: {current_round['total_pot']:.3f} SOL\n"
                    f"📈 PUMP: {current_round['pump_pot']:.3f} SOL ({pump_pct:.1f}%)\n"
                    f"📉 DUMP: {current_round['dump_pot']:.3f} SOL ({dump_pct:.1f}%)\n"
                    f"👥 Players: {len(current_round['bets'])}\n\n"
                    f"🎲 **Revealing result in 15 seconds...**\n"
                    f"📊 **Watch the Live Chart for dramatic animation!**"
                )
            
            print(f"🎯 Round #{round_number} - Revealing (15s)")
            
            await asyncio.sleep(15)
            
            import random
            result = random.choice(['PUMP', 'DUMP'])
            result_emoji = "📈" if result == 'PUMP' else "📉"
            
            print(f"📊 Round #{round_number} result: {result}")
            
            # Process results
            winner_count = 0
            if current_round['bets']:
                winners = {uid: bet for uid, bet in current_round['bets'].items() if bet['type'] == result}
                losers = {uid: bet for uid, bet in current_round['bets'].items() if bet['type'] != result}
                
                total_pot = current_round['total_pot']
                house_cut = total_pot * 0.05
                winners_pool = total_pot - house_cut
                
                if winners:
                    winning_amount = current_round['pump_pot'] if result == 'PUMP' else current_round['dump_pot']
                    multiplier = winners_pool / winning_amount if winning_amount > 0 else 0
                    
                    print(f"💰 {len(winners)} winners, {multiplier:.3f}x multiplier")
                    winner_count = len(winners)
                    
                    for user_id, bet in winners.items():
                        payout = bet['amount'] * multiplier
                        async with db.pool.acquire() as conn:
                            await conn.execute(
                                "UPDATE users SET balance = balance + $1, wins = wins + 1, games_played = games_played + 1, total_won = total_won + $2 WHERE telegram_id = $3",
                                Decimal(str(payout)), Decimal(str(payout)), user_id
                            )
                        print(f"💸 Paid {bet['user']}: {payout:.6f} SOL")
                    
                    for user_id in losers:
                        async with db.pool.acquire() as conn:
                            await conn.execute(
                                "UPDATE users SET losses = losses + 1, games_played = games_played + 1 WHERE telegram_id = $1",
                                user_id
                            )
                    
                    result_text = f"""
🏆 **ROUND #{round_number} RESULT**

{result_emoji} **{result} WINS!** {result_emoji}

**Final Stats:**
💰 Total Pot: {total_pot:.3f} SOL
🏠 House Fee (5%): {house_cut:.3f} SOL  
🎉 Winners Pool: {winners_pool:.3f} SOL
📊 Multiplier: **{multiplier:.3f}x**

🎉 **{len(winners)} winner(s) paid!**
😢 {len(losers)} lost this round

📊 **Amazing animation on the Live Chart!**
💡 Next round starting in 3 seconds...
                    """
                    
                else:
                    result_text = f"""
🏆 **ROUND #{round_number} RESULT**

{result_emoji} **{result} WINS!** {result_emoji}

😢 **No winners this round!**
🏠 House keeps all {total_pot:.3f} SOL

💡 Better luck next time!
📊 **Check out the Live Chart animation!**
Next round starting in 3 seconds...
                    """
                    
                    for user_id in current_round['bets']:
                        async with db.pool.acquire() as conn:
                            await conn.execute(
                                "UPDATE users SET losses = losses + 1, games_played = games_played + 1 WHERE telegram_id = $1",
                                user_id
                            )
                
                await notify_betting_users(result_text)
                
            # 🚀 NOTIFY WEBSOCKET OF RESULT
            await websocket_server.update_round_result(
                round_number=round_number,
                result=result,
                total_pot=current_round['total_pot'],
                winner_count=winner_count
            )
            
            current_round['status'] = 'completed'
            print(f"✅ Round #{round_number} completed - Next round auto-starting...")
            round_number += 1
            
            await asyncio.sleep(3)
            
        except Exception as e:
            print(f"❌ Game loop error: {e}")
            logger.error(f"Game loop error: {e}")
            await asyncio.sleep(5)

async def main():
    """Main function with Web App integration"""
    print("🎰 STARTING ULTIMATE PUMP OR DUMP BOT WITH TELEGRAM WEB APP!")
    print(f"📱 Bot: @{Config.BOT_USERNAME}")
    print(f"📊 Web App: {CHART_WEB_APP_URL}")
    print("🚀 Real-time chart integration enabled!")
    
    await db.init_pool()
    print("✅ Database connected")
    # Start WebSocket server
    #websocket_task = asyncio.create_task(websocket_server.start_server())
    #print("🔌 WebSocket server starting...")
    
    await asyncio.sleep(2)  # Give WebSocket time to start
    
    game_task = asyncio.create_task(game_loop())
    
    try:
        print("🎰 Ultimate bot with Telegram Web App started!")
        print("📊 Users can access live chart directly in Telegram!") 
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\n⚠️ Bot stopped")
    finally:
        game_task.cancel()
        websocket_task.cancel()
        await db.close_pool()
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
