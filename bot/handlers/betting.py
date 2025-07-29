from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.config import Config, GameConstants
from bot.services.database import db
from bot.services.game_manager import game_manager

router = Router()

class BettingStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_bet_type = State()

def get_betting_keyboard() -> InlineKeyboardMarkup:
    """Get the betting options keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📈 PUMP", callback_data="bet_PUMP"),
            InlineKeyboardButton(text="📉 DUMP", callback_data="bet_DUMP")
        ],
        [
            InlineKeyboardButton(text="💰 Quick Bet 0.1", callback_data="quick_bet_0.1_PUMP"),
            InlineKeyboardButton(text="💰 Quick Bet 0.1", callback_data="quick_bet_0.1_DUMP")
        ],
        [
            InlineKeyboardButton(text="🔄 Refresh", callback_data="refresh_round"),
            InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")
        ]
    ])
    return keyboard

def get_amount_keyboard() -> InlineKeyboardMarkup:
    """Get the bet amount selection keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="0.01", callback_data="amount_0.01"),
            InlineKeyboardButton(text="0.05", callback_data="amount_0.05"),
            InlineKeyboardButton(text="0.1", callback_data="amount_0.1")
        ],
        [
            InlineKeyboardButton(text="0.5", callback_data="amount_0.5"),
            InlineKeyboardButton(text="1.0", callback_data="amount_1.0"),
            InlineKeyboardButton(text="2.0", callback_data="amount_2.0")
        ],
        [
            InlineKeyboardButton(text="💬 Custom Amount", callback_data="custom_amount"),
            InlineKeyboardButton(text="🔙 Back", callback_data="play")
        ]
    ])
    return keyboard

def get_confirm_keyboard(bet_type: str, amount: float) -> InlineKeyboardMarkup:
    """Get bet confirmation keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"✅ Confirm {GameConstants.BET_TYPES[bet_type]} {amount}",
                callback_data=f"confirm_bet_{bet_type}_{amount}"
            )
        ],
        [
            InlineKeyboardButton(text="🔙 Back", callback_data="play"),
            InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")
        ]
    ])
    return keyboard

async def get_round_status_text():
    """Get current round status as formatted text"""
    current_round = await game_manager.get_current_round_info()
    
    if not current_round:
        return "⏳ **Waiting for next round...**\n\nNew round starting soon!"
    
    if current_round['status'] == 'betting':
        text = f"🔥 **ROUND #{current_round['round_number']} - BETTING OPEN**\n\n"
        text += f"⏱️ **Time Remaining:** {current_round['time_remaining']}s\n"
        text += f"💰 **Total Pot:** {current_round['total_pot']:.3f} SOL\n"
        text += f"👥 **Players:** {current_round['participants_count']}\n\n"
        
        if current_round['total_pot'] > 0:
            text += f"📈 **PUMP Bets:** {current_round['pump_pot']:.3f} SOL ({current_round['pump_percentage']:.1f}%)\n"
            text += f"📉 **DUMP Bets:** {current_round['dump_pot']:.3f} SOL ({current_round['dump_percentage']:.1f}%)\n\n"
        
        text += "**Choose your side:**"
        
    elif current_round['status'] == 'revealing':
        text = f"🎲 **ROUND #{current_round['round_number']} - REVEALING**\n\n"
        text += f"💰 **Total Pot:** {current_round['total_pot']:.3f} SOL\n"
        text += f"📈 **PUMP:** {current_round['pump_pot']:.3f} SOL ({current_round['pump_percentage']:.1f}%)\n"
        text += f"📉 **DUMP:** {current_round['dump_pot']:.3f} SOL ({current_round['dump_percentage']:.1f}%)\n\n"
        text += "🎯 **Determining result...**\n"
        text += "⏳ Please wait for the next round!"
    
    else:
        text = "⏳ **Round transition...**\n\nNext round starting soon!"
    
    return text

@router.message(Command("play"))
async def play_command(message: Message):
    """Handle /play command"""
    await show_play_interface(message)

@router.callback_query(F.data == "play")
async def play_callback(callback: CallbackQuery):
    """Handle play button callback"""
    await show_play_interface(callback.message, callback)

async def show_play_interface(message: Message, callback: CallbackQuery = None):
    """Show the main play interface"""
    # Get user info
    user = await db.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    
    # Check if user has bet in current round
    current_bet = await game_manager.get_user_current_bet(message.from_user.id)
    
    status_text = await get_round_status_text()
    
    if current_bet:
        status_text += f"\n\n💰 **Your Bet:** {GameConstants.BET_TYPES[current_bet['bet_type']]} {current_bet['amount']} SOL"
        status_text += f"\n💳 **Balance:** {user['balance']:.3f} SOL"
    else:
        status_text += f"\n\n💳 **Your Balance:** {user['balance']:.3f} SOL"
        status_text += f"\n💡 **Bet Range:** {Config.MIN_BET} - {Config.MAX_BET} SOL"
    
    if callback:
        await callback.message.edit_text(
            status_text,
            reply_markup=get_betting_keyboard()
        )
        await callback.answer()
    else:
        await message.answer(
            status_text,
            reply_markup=get_betting_keyboard()
        )

@router.callback_query(F.data.startswith("bet_"))
async def bet_type_callback(callback: CallbackQuery, state: FSMContext):
    """Handle bet type selection"""
    bet_type = callback.data.split("_")[1]  # bet_PUMP -> PUMP
    
    # Check if betting is available
    can_bet, message_text = await game_manager.can_place_bet(callback.from_user.id, Config.MIN_BET)
    
    if not can_bet:
        await callback.answer(message_text, show_alert=True)
        return
    
    # Store bet type in state
    await state.set_data({"bet_type": bet_type})
    
    # Show amount selection
    user = await db.get_or_create_user(callback.from_user.id)
    
    amount_text = f"📊 **Select Bet Amount**\n\n"
    amount_text += f"**Side:** {GameConstants.BET_TYPES[bet_type]}\n"
    amount_text += f"**Your Balance:** {user['balance']:.3f} SOL\n"
    amount_text += f"**Min/Max:** {Config.MIN_BET} - {Config.MAX_BET} SOL\n\n"
    amount_text += "Choose an amount or enter custom:"
    
    await callback.message.edit_text(
        amount_text,
        reply_markup=get_amount_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("amount_"))
async def amount_callback(callback: CallbackQuery, state: FSMContext):
    """Handle bet amount selection"""
    amount = float(callback.data.split("_")[1])  # amount_0.1 -> 0.1
    
    # Get bet type from state
    data = await state.get_data()
    bet_type = data.get("bet_type")
    
    if not bet_type:
        await callback.answer("❌ Please select bet type first", show_alert=True)
        return
    
    # Show confirmation
    confirm_text = f"🎯 **Confirm Your Bet**\n\n"
    confirm_text += f"**Side:** {GameConstants.BET_TYPES[bet_type]}\n"
    confirm_text += f"**Amount:** {amount} SOL\n\n"
    
    current_round = await game_manager.get_current_round_info()
    if current_round:
        confirm_text += f"**Round:** #{current_round['round_number']}\n"
        confirm_text += f"**Time Left:** {current_round['time_remaining']}s\n\n"
    
    confirm_text += "⚠️ **This action cannot be undone!**"
    
    await callback.message.edit_text(
        confirm_text,
        reply_markup=get_confirm_keyboard(bet_type, amount)
    )
    await callback.answer()

@router.callback_query(F.data == "custom_amount")
async def custom_amount_callback(callback: CallbackQuery, state: FSMContext):
    """Handle custom amount input"""
    await state.set_state(BettingStates.waiting_for_amount)
    
    await callback.message.edit_text(
        f"💬 **Enter Custom Amount**\n\n"
        f"Send a message with your bet amount\n"
        f"**Range:** {Config.MIN_BET} - {Config.MAX_BET} SOL\n\n"
        f"**Example:** `0.25`"
    )
    await callback.answer()

@router.message(BettingStates.waiting_for_amount)
async def process_custom_amount(message: Message, state: FSMContext):
    """Process custom bet amount"""
    try:
        amount = float(message.text.strip())
        
        # Validate amount
        if amount < Config.MIN_BET or amount > Config.MAX_BET:
            await message.answer(f"❌ Amount must be between {Config.MIN_BET} and {Config.MAX_BET} SOL")
            return
        
        # Get bet type from state
        data = await state.get_data()
        bet_type = data.get("bet_type")
        
        if not bet_type:
            await message.answer("❌ Please start over with /play")
            await state.clear()
            return
        
        # Clear state
        await state.clear()
        
        # Show confirmation
        confirm_text = f"🎯 **Confirm Your Bet**\n\n"
        confirm_text += f"**Side:** {GameConstants.BET_TYPES[bet_type]}\n"
        confirm_text += f"**Amount:** {amount} SOL\n\n"
        
        current_round = await game_manager.get_current_round_info()
        if current_round:
            confirm_text += f"**Round:** #{current_round['round_number']}\n"
            confirm_text += f"**Time Left:** {current_round['time_remaining']}s\n\n"
        
        confirm_text += "⚠️ **This action cannot be undone!**"
        
        await message.answer(
            confirm_text,
            reply_markup=get_confirm_keyboard(bet_type, amount)
        )
        
    except ValueError:
        await message.answer("❌ Please enter a valid number (e.g., 0.5)")

@router.callback_query(F.data.startswith("confirm_bet_"))
async def confirm_bet_callback(callback: CallbackQuery):
    """Handle bet confirmation"""
    # Parse callback data: confirm_bet_PUMP_0.5
    parts = callback.data.split("_")
    bet_type = parts[2]
    amount = float(parts[3])
    
    # Place the bet
    success, message_text = await game_manager.place_bet(
        callback.from_user.id, 
        bet_type, 
        amount
    )
    
    if success:
        # Show success message
        success_text = f"✅ **Bet Placed Successfully!**\n\n"
        success_text += f"**Side:** {GameConstants.BET_TYPES[bet_type]}\n"
        success_text += f"**Amount:** {amount} SOL\n\n"
        success_text += f"🍀 **Good luck!** Results coming soon...\n\n"
        success_text += "You can watch the live chart or wait for the result!"
        
        # Create result keyboard
        result_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📈 Live Chart", url="http://localhost:3000"),
                InlineKeyboardButton(text="🔄 Refresh", callback_data="refresh_round")
            ],
            [
                InlineKeyboardButton(text="📊 My Stats", callback_data="stats"),
                InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")
            ]
        ])
        
        await callback.message.edit_text(
            success_text,
            reply_markup=result_keyboard
        )
        await callback.answer("🎉 Bet placed! Good luck!")
        
    else:
        await callback.answer(message_text, show_alert=True)

@router.callback_query(F.data.startswith("quick_bet_"))
async def quick_bet_callback(callback: CallbackQuery):
    """Handle quick bet buttons"""
    # Parse: quick_bet_0.1_PUMP
    parts = callback.data.split("_")
    amount = float(parts[2])
    bet_type = parts[3]
    
    # Place bet immediately
    success, message_text = await game_manager.place_bet(
        callback.from_user.id,
        bet_type,
        amount
    )
    
    if success:
        await callback.answer(f"✅ Quick bet placed: {GameConstants.BET_TYPES[bet_type]} {amount} SOL!")
        # Refresh the interface
        await show_play_interface(callback.message, callback)
    else:
        await callback.answer(message_text, show_alert=True)

@router.callback_query(F.data == "refresh_round")
async def refresh_round_callback(callback: CallbackQuery):
    """Handle round refresh"""
    await show_play_interface(callback.message, callback)

@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery):
    """Handle main menu button"""
    from bot.handlers.start import get_main_keyboard
    from bot.config import Messages
    
    await callback.message.edit_text(
        Messages.WELCOME,
        reply_markup=get_main_keyboard()
    )
    await callback.answer()