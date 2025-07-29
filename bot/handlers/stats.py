from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from bot.services.database import db
from datetime import datetime, timedelta

router = Router()

def get_stats_keyboard() -> InlineKeyboardMarkup:
    """Get the statistics menu keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 My Stats", callback_data="my_stats"),
            InlineKeyboardButton(text="🏆 Leaderboard", callback_data="leaderboard")
        ],
        [
            InlineKeyboardButton(text="📈 Recent Rounds", callback_data="recent_rounds"),
            InlineKeyboardButton(text="💰 Game Stats", callback_data="game_stats")
        ],
        [
            InlineKeyboardButton(text="🎮 Play Now", callback_data="play"),
            InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")
        ]
    ])
    return keyboard

@router.message(Command("stats"))
async def stats_command(message: Message):
    """Handle /stats command"""
    await show_stats_menu(message)

@router.callback_query(F.data == "stats")
async def stats_callback(callback: CallbackQuery):
    """Handle stats button callback"""
    await show_stats_menu(callback.message, callback)

async def show_stats_menu(message: Message, callback: CallbackQuery = None):
    """Show the stats menu"""
    stats_text = """
📊 **Statistics Menu**

Choose what you'd like to see:

📊 **My Stats** - Your personal statistics
🏆 **Leaderboard** - Top players
📈 **Recent Rounds** - Latest game results  
💰 **Game Stats** - Overall game statistics

What would you like to check?
    """
    
    if callback:
        await callback.message.edit_text(
            stats_text,
            reply_markup=get_stats_keyboard()
        )
        await callback.answer()
    else:
        await message.answer(
            stats_text,
            reply_markup=get_stats_keyboard()
        )

@router.callback_query(F.data == "my_stats")
async def my_stats_callback(callback: CallbackQuery):
    """Handle my stats callback"""
    # Get user stats
    user_stats = await db.get_user_stats(callback.from_user.id)
    
    if not user_stats:
        stats_text = "📊 **Your Statistics**\n\nNo game data found. Start playing to see your stats!"
    else:
        # Calculate additional metrics
        profit_loss = user_stats['total_won'] - user_stats['total_wagered']
        avg_bet = user_stats['total_wagered'] / user_stats['games_played'] if user_stats['games_played'] > 0 else 0
        
        # Determine status emoji
        if profit_loss > 0:
            status_emoji = "🟢"
            status_text = "Profitable"
        elif profit_loss < 0:
            status_emoji = "🔴" 
            status_text = "At Loss"
        else:
            status_emoji = "🟡"
            status_text = "Break Even"
        
        stats_text = f"""
📊 **Your Statistics**

💰 **Current Balance:** {user_stats['balance']:.6f} SOL
{status_emoji} **Status:** {status_text}

**🎮 Game Performance:**
• Games Played: {user_stats['games_played']}
• Wins: {user_stats['wins']} 🏆
• Losses: {user_stats['losses']} 😢
• Win Rate: {user_stats['win_rate']:.1f}%

**💸 Financial Summary:**
• Total Wagered: {user_stats['total_wagered']:.6f} SOL
• Total Won: {user_stats['total_won']:.6f} SOL  
• Net Profit/Loss: {profit_loss:+.6f} SOL
• Average Bet: {avg_bet:.6f} SOL

**📈 Performance Rating:**
{get_performance_rating(user_stats['win_rate'], profit_loss)}
        """
    
    await callback.message.edit_text(
        stats_text,
        reply_markup=get_stats_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "leaderboard") 
async def leaderboard_callback(callback: CallbackQuery):
    """Handle leaderboard callback"""
    # Get top players
    async with db.pool.acquire() as conn:
        top_players = await conn.fetch("""
            SELECT 
                username, first_name,
                total_won - total_wagered as profit,
                games_played,
                wins,
                CASE WHEN games_played > 0 THEN ROUND((wins::float / games_played::float) * 100, 1) ELSE 0 END as win_rate
            FROM users 
            WHERE games_played >= 5
            ORDER BY (total_won - total_wagered) DESC
            LIMIT 10
        """)
    
    if not top_players:
        leaderboard_text = "🏆 **Leaderboard**\n\nNot enough players yet. Be the first to play 5+ games!"
    else:
        leaderboard_text = "🏆 **Top Players (Profit)**\n\n"
        
        for i, player in enumerate(top_players, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            username = player['username'] or player['first_name'] or "Anonymous"
            
            leaderboard_text += f"{medal} **{username}**\n"
            leaderboard_text += f"   💰 {player['profit']:+.3f} SOL | "
            leaderboard_text += f"🎮 {player['games_played']} games | "
            leaderboard_text += f"📊 {player['win_rate']:.1f}% WR\n\n"
        
        # Show user's rank if not in top 10
        async with db.pool.acquire() as conn:
            user_rank = await conn.fetchrow("""
                SELECT rank FROM (
                    SELECT 
                        telegram_id,
                        ROW_NUMBER() OVER (ORDER BY (total_won - total_wagered) DESC) as rank
                    FROM users 
                    WHERE games_played >= 5
                ) ranked 
                WHERE telegram_id = $1
            """, callback.from_user.id)
            
            if user_rank and user_rank['rank'] > 10:
                leaderboard_text += f"\n📍 **Your Rank:** #{user_rank['rank']}"
    
    await callback.message.edit_text(
        leaderboard_text,
        reply_markup=get_stats_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "recent_rounds")
async def recent_rounds_callback(callback: CallbackQuery):
    """Handle recent rounds callback"""
    recent_rounds = await db.get_recent_rounds(15)
    
    if not recent_rounds:
        rounds_text = "📈 **Recent Rounds**\n\nNo completed rounds yet."
    else:
        rounds_text = "📈 **Recent Rounds**\n\n"
        
        for round_data in recent_rounds:
            result_emoji = "📈" if round_data['result'] == 'PUMP' else "📉"
            time_str = round_data['ended_at'].strftime('%H:%M')
            
            rounds_text += f"**#{round_data['round_number']}** {result_emoji} {round_data['result']}\n"
            rounds_text += f"💰 {round_data['total_pot']:.3f} SOL | "
            rounds_text += f"👥 {round_data['participants_count']} | "
            rounds_text += f"🕐 {time_str}\n\n"
    
    await callback.message.edit_text(
        rounds_text,
        reply_markup=get_stats_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "game_stats")
async def game_stats_callback(callback: CallbackQuery):
    """Handle game stats callback"""
    # Get overall game statistics
    async with db.pool.acquire() as conn:
        # Today's stats
        today_stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as rounds_today,
                COALESCE(SUM(total_pot), 0) as volume_today,
                COALESCE(SUM(house_profit), 0) as house_profit_today,
                COUNT(DISTINCT r.id) filter (where r.participants_count > 0) as active_rounds_today
            FROM rounds r
            WHERE DATE(r.ended_at) = CURRENT_DATE
            AND r.status = 'completed'
        """)
        
        # All time stats
        all_time_stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_rounds,
                COALESCE(SUM(total_pot), 0) as total_volume,
                COALESCE(SUM(house_profit), 0) as total_house_profit,
                COALESCE(AVG(total_pot), 0) as avg_pot_size,
                COUNT(DISTINCT r.id) filter (where r.participants_count > 0) as active_rounds
            FROM rounds r
            WHERE r.status = 'completed'
        """)
        
        # User stats
        user_stats = await conn.fetchrow("""
            SELECT 
                COUNT(DISTINCT telegram_id) as total_users,
                COUNT(DISTINCT telegram_id) filter (where games_played > 0) as active_users,
                COUNT(DISTINCT telegram_id) filter (where DATE(updated_at) = CURRENT_DATE) as daily_active_users
            FROM users
        """)
        
        # Result distribution
        result_stats = await conn.fetch("""
            SELECT 
                result,
                COUNT(*) as count,
                ROUND((COUNT(*)::float / (SELECT COUNT(*) FROM rounds WHERE status = 'completed' AND result IS NOT NULL)::float) * 100, 1) as percentage
            FROM rounds 
            WHERE status = 'completed' AND result IS NOT NULL
            GROUP BY result
            ORDER BY count DESC
        """)
    
    # Format the stats
    stats_text = f"""
💰 **Game Statistics**

**📊 Today's Activity:**
• Rounds Completed: {today_stats['rounds_today']}
• Total Volume: {today_stats['volume_today']:.3f} SOL
• House Profit: {today_stats['house_profit_today']:.3f} SOL
• Active Rounds: {today_stats['active_rounds_today']}

**🏆 All Time:**
• Total Rounds: {all_time_stats['total_rounds']}
• Total Volume: {all_time_stats['total_volume']:.3f} SOL
• House Profit: {all_time_stats['total_house_profit']:.3f} SOL
• Average Pot: {all_time_stats['avg_pot_size']:.3f} SOL

**👥 Player Stats:**
• Total Users: {user_stats['total_users']}
• Active Players: {user_stats['active_users']}
• Daily Active: {user_stats['daily_active_users']}

**📈 Result Distribution:**
"""
    
    for result in result_stats:
        emoji = "📈" if result['result'] == 'PUMP' else "📉"
        stats_text += f"• {emoji} {result['result']}: {result['count']} ({result['percentage']}%)\n"
    
    await callback.message.edit_text(
        stats_text,
        reply_markup=get_stats_keyboard()
    )
    await callback.answer()

def get_performance_rating(win_rate: float, profit: float) -> str:
    """Get performance rating based on win rate and profit"""
    if win_rate >= 60 and profit > 1:
        return "🌟 **Legendary** - Outstanding performance!"
    elif win_rate >= 55 and profit > 0.5:
        return "💎 **Expert** - Excellent skills!"
    elif win_rate >= 50 and profit > 0:
        return "🔥 **Pro** - Above average player!"
    elif win_rate >= 45:
        return "⚡ **Skilled** - Good performance!"
    elif win_rate >= 40:
        return "📈 **Learning** - Keep improving!"
    else:
        return "🎯 **Beginner** - Practice makes perfect!"

@router.message(Command("balance"))
async def balance_command(message: Message):
    """Handle /balance command"""
    user_stats = await db.get_user_stats(message.from_user.id)
    
    if user_stats:
        balance_text = f"""
💰 **Balance Summary**

**Current Balance:** {user_stats['balance']:.6f} SOL
**Total Wagered:** {user_stats['total_wagered']:.6f} SOL
**Total Won:** {user_stats['total_won']:.6f} SOL
**Net P&L:** {(user_stats['total_won'] - user_stats['total_wagered']):+.6f} SOL

💡 *Use /play to join the next round!*
        """
    else:
        balance_text = "💰 **Balance:** 1.000000 SOL\n\nWelcome! Use /play to start betting!"
    
    await message.answer(balance_text)