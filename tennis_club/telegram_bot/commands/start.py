
async def start(update, context):
    """ Admin panel"""
    await update.message.reply_text(
        "Useful links:"
        "\nFor Subscribe to receive Bot Notifications:"
        "\n/get_notifications"
        "\n"
        "\nGet Information about trainings:"
        "\n* by current month: /get_month_training"
        "\n* reserved: /get_reserved_training"
        "\n"
        "\nGet Information about money:"
        "\n* balance: /get_balance"
    )