await query.edit_message_text(
        f"✅ {state['name']} · {state['shift']} смена\n\nНачинаем чек-лист!",
        parse_mode="Markdown"
    )
    si = 0
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=section_text(si, state),
        parse_mode="Markdown",
        reply_markup=build_section_keyboard(si, state)
    )
    return CHECKLIST


async def handle_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = get_user_state(user_id)

    data = query.data
    if data.startswith("toggle:"):
        _, si, ii = data.split(":")
        key = f"{si}-{ii}"
        state["checks"][key] = not state["checks"].get(key, False)
        si = int(si)
        await query.edit_message_text(
            text=section_text(si, state),
            parse_mode="Markdown",
            reply_markup=build_section_keyboard(si, state)
        )

    elif data.startswith("section:"):
        si = int(data.split(":")[1])
        state["current_section"] = si
        await query.edit_message_text(
            text=section_text(si, state),
            parse_mode="Markdown",
            reply_markup=build_section_keyboard(si, state)
        )

    elif data == "report":
        report = build_report(state)
        await query.message.reply_text(report, parse_mode="Markdown")

        # Отправить руководителю если настроен MANAGER_CHAT_ID
        if MANAGER_CHAT_ID:
            try:
                await context.bot.send_message(
                    chat_id=int(MANAGER_CHAT_ID),
                    text=f"📬 *Новый отчёт от повара:*\n\n{report}",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Не удалось отправить руководителю: {e}")

    return CHECKLIST


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start(update, context)


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_SHIFT: [CallbackQueryHandler(ask_shift, pattern="^shift:")],
            CHECKLIST: [CallbackQueryHandler(handle_toggle)],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("reset", reset)],
    )

    app.add_handler(conv)
    logger.info("Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
