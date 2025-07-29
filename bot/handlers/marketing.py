from aiogram import Router, types, F
from datetime import datetime, timedelta

router = Router()

@router.message(Command("rain"))
async def rain_command(message: types.Message):
    """Winner can rain SOL on chat members"""
    user_id = message.from_user.id
    
    # Check if user won recently
    recent_win = await db.get_user_recent_win(user_id)
    if not recent_win or recent_win['amount'] < 5:
        await message.reply("☔ You need to win at least 5 SOL to make it rain!")
        return
    
    # Get active users in chat
    active_users = await db.get_active_chat_users(message.chat.id)
    rain_amount = min(recent_win['amount'] * 0.1, 10)  # 10% of win, max 10 SOL
    amount_per_user = rain_amount / len(active_users)
    
    # Distribute rain
    for user in active_users:
        await db.add_user_balance(user['id'], amount_per_user)
    
    await message.reply(
        f"🌧️ {message.from_user.first_name} MAKES IT RAIN!\n"
        f"💰 {rain_amount:.2f} SOL shared with {len(active_users)} users!\n"
        f"🎉 Everyone gets {amount_per_user:.3f} SOL!"
    )

@router.message(Command("leaderboard"))
async def leaderboard_command(message: types.Message):
    """Show daily/weekly/all-time leaderboards"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Daily", callback_data="lb_daily"),
            InlineKeyboardButton(text="📆 Weekly", callback_data="lb_weekly"),
            InlineKeyboardButton(text="🏆 All-Time", callback_data="lb_alltime")
        ]
    ])
    
    await message.reply("🏆 Choose leaderboard:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("lb_"))
async def show_leaderboard(callback: types.CallbackQuery):
    """Display the actual leaderboard"""
    period = callback.data.split("_")[1]
    
    leaders = await db.get_leaderboard(period, limit=10)
    
    text = f"🏆 **{period.upper()} LEADERBOARD**\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    for i, leader in enumerate(leaders):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += (
            f"{medal} @{leader['username']} - "
            f"**+{leader['profit']:.2f} SOL**\n"
            f"   Win Rate: {leader['win_rate']}% | "
            f"Biggest Win: {leader['biggest_win']:.2f} SOL\n\n"
        )
    
    await callback.message.edit_text(text, parse_mode="Markdown")