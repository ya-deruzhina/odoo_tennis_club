from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler, filters,
    ConversationHandler, CallbackQueryHandler
)
from .check_customer_data import check_customer_data

ID_CARD, EMAIL, CONSENT, CONTINUE_WITHOUT_NOTIF = range(4)


async def ask_id_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Ask ID card"""
    await update.message.reply_text("Please enter your ID Card:")
    return ID_CARD


async def ask_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Ask Email"""
    context.user_data["id_card"] = update.message.text
    await update.message.reply_text("Please enter your email:")
    return EMAIL


async def ask_consent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ ASK Conset """
    context.user_data["email"] = update.message.text

    keyboard = [
        [
            InlineKeyboardButton("YES", callback_data="consent_yes"),
            InlineKeyboardButton("NO", callback_data="consent_no")
        ]
    ]

    await update.message.reply_text(
        "Do you agree to the processing of personal data and receiving notifications?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONSENT


async def handle_consent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Handle Consent """
    query = update.callback_query
    await query.answer()

    if query.data == "consent_no":
        context.user_data["permission_to_notify"] = False

        keyboard = [
            [
                InlineKeyboardButton("Continue without notifications", callback_data="continue_no_notif"),
                InlineKeyboardButton("Cancel", callback_data="cancel_no_notif")
            ]
        ]

        await query.edit_message_text(
            "You will NOT receive notifications.\n"
            "Do you want to continue registration?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return CONTINUE_WITHOUT_NOTIF

    else:
        context.user_data["permission_to_notify"] = True
        return await complete_registration(query, context)


async def handle_continue_without_notif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Handle Continue Without Notification """
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_no_notif":
        await query.edit_message_text("Registration cancelled")
        return ConversationHandler.END

    elif query.data == "continue_no_notif":
        return await complete_registration(query, context)


async def complete_registration(query, context):
    """ Complete Registration """
    id_card = context.user_data["id_card"]
    email = context.user_data["email"]
    permission = context.user_data["permission_to_notify"]
    chat_id = query.message.chat.id

    check_data = check_customer_data(id_card, email, chat_id, permission)

    if check_data["status"] == "OK":
        await query.edit_message_text(
            f"Thank you for Registration!\n"
            f"ID Card: {id_card}\n"
            f"Email: {email}\n"
            f"Name: {check_data['name']}\n"
            f"Notifications allowed: {permission}"
        )
    else:
        await query.edit_message_text(
            "Registration failed. User not found or chat already assigned."
        )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Cancel """
    await update.message.reply_text("Registration cancelled")
    return ConversationHandler.END


get_notifications = ConversationHandler(
    entry_points=[CommandHandler("get_notifications", ask_id_card)],
    states={
        ID_CARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
        EMAIL:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_consent)],
        CONSENT: [CallbackQueryHandler(handle_consent)],
        CONTINUE_WITHOUT_NOTIF: [CallbackQueryHandler(handle_continue_without_notif)],
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)
