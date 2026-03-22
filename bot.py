import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "ВАШ_ТОКЕН")
MANAGER_CHAT_ID = os.environ.get("MANAGER_CHAT_ID", "")
SECTIONS = [{"icon": "🌅", "title": "ОТКРЫТИЕ СМЕНЫ", "items": [{"text": "Принять смену у предыдущего повара"},{"text": "Проверить температуру холодильников", "note": "0-4C / -18C"},{"text": "Проверить сроки годности продуктов"},{"text": "Провести инвентаризацию и заявку на склад"},{"text": "Проверить чистоту кухни"},{"text": "Проверить исправность оборудования"},{"text": "Прогреть оборудование", "note": "Фритюр 175-180C"}]},{"icon": "🧑‍🍳", "title": "УПРАВЛЕНИЕ КОМАНДОЙ", "items": [{"text": "Провести планёрку перед сменой"},{"text": "Распределить зоны ответственности"},{"text": "Проверить наличие сотрудников по расписанию"},{"text": "Проверить опрятный вид и форму"},{"text": "Контролировать скорость работы в часы пик"},{"text": "Фиксировать нарушения стандартов"}]},{"icon": "🥩", "title": "ЗАГОТОВКИ И ПРОДУКТЫ", "items": [{"text": "Проверить наличие заготовок на смену"},{"text": "Контролировать разморозку полуфабрикатов"},{"text": "Проверить соблюдение FIFO"},{"text": "Контролировать вес и объём порций"},{"text": "Проверить маркировку заготовок"}]},{"icon": "🛡️", "title": "КАЧЕСТВО И БЕЗОПАСНОСТЬ", "items": [{"text": "Контролировать температуру при жарке", "note": "t внутри >= 75C"},{"text": "Провести бракераж готовых блюд"},{"text": "Следить за сроками хранения на раздаче"},{"text": "Контролировать мытьё рук и перчатки"},{"text": "Проверить санитайзеры"},{"text": "Замер температуры масла в журнал"}]},{"icon": "🧹", "title": "ЧИСТОТА И ПОРЯДОК", "items": [{"text": "Уборка рабочих поверхностей", "note": "Каждый час"},{"text": "Вывоз мусора"},{"text": "Чистота фритюрниц и грилей"},{"text": "Порядок в холодильных камерах"},{"text": "Пол и стены в зоне кухни"}]},{"icon": "📋", "title": "ДОКУМЕНТАЦИЯ", "items": [{"text": "Журнал температурного контроля"},{"text": "Записать списание продуктов"},{"text": "Отметить выполнение уборок"},{"text": "Передать расход продуктов на склад"}]},{"icon": "🌙", "title": "ЗАКРЫТИЕ СМЕНЫ", "items": [{"text": "Инвентаризация остатков"},{"text": "Утилизация неиспользованных блюд"},{"text": "Финальная уборка кухни"},{"text": "Отключить и почистить оборудование"},{"text": "Передать смену следующему повару"},{"text": "Подписать итоговый чек-лист"}]}]
ASK_NAME, ASK_SHIFT, CHECKLIST = range(3)
user_data_store = {}
def get_user_state(user_id):
    if user_id not in user_data_store:
        user_data_store[user_id] = {"name": None, "shift": None, "checks": {}, "current_section": 0}
    return user_data_store[user_id]
def build_report(state):
    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y %H:%M")
    total = sum(len(s["items"]) for s in SECTIONS)
    done = sum(1 for v in state["checks"].values() if v)
    pct = round(done / total * 100) if total else 0
    lines = ["🍔 *ЧЕК-ЛИСТ СТАРШЕГО ПОВАРА*", f"👤 {state['name']} · {state['shift']} смена", f"📅 {date_str}", f"✅ Выполнено: {done}/{total} ({pct}%)", "---", ""]
    for si, sec in enumerate(SECTIONS):
        lines.append(f"{sec['icon']} *{sec['title']}*")
        for ii, item in enumerate(sec["items"]):
            mark = "✅" if state["checks"].get(f"{si}-{ii}") else "⬜"
            lines.append(f"{mark} {item['text']}")
        lines.append("")
    lines.append("---")
    lines.append("🔥 *СМЕНА ПРИНЯТА!*" if pct == 100 else f"⚠️ Выполнено {pct}%")
    return "\n".join(lines)
def build_section_keyboard(si, state):
    sec = SECTIONS[si]
    keyboard = []
    for ii, item in enumerate(sec["items"]):
        key = f"{si}-{ii}"
        mark = "✅" if state["checks"].get(key) else "⬜"
        keyboard.append([InlineKeyboardButton(f"{mark} {item['text'][:45]}", callback_data=f"toggle:{si}:{ii}")])
    nav = []
    if si > 0:
        nav.append(InlineKeyboardButton("◀ Назад", callback_data=f"section:{si-1}"))
    if si < len(SECTIONS) - 1:
        nav.append(InlineKeyboardButton("Далее ▶", callback_data=f"section:{si+1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("📤 Отправить отчёт", callback_data="report")])
    return InlineKeyboardMarkup(keyboard)
def section_text(si, state):
    sec = SECTIONS[si]
    total_sec = len(sec["items"])
    done_sec = sum(1 for ii in range(total_sec) if state["checks"].get(f"{si}-{ii}"))
    total_all = sum(len(s["items"]) for s in SECTIONS)
    done_all = sum(1 for v in state["checks"].values() if v)
    return f"{sec['icon']} *{sec['title']}*\n_{done_sec}/{total_sec} в разделе · {done_all}/{total_all} всего_\n\nРаздел {si+1} из {len(SECTIONS)}"
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data_store[user_id] = {"name": None, "shift": None, "checks": {}, "current_section": 0}
    await update.message.reply_text("👋 Привет! Я бот чек-листа старшего повара.\n\nКак тебя зовут?")
    return ASK_NAME
async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    state["name"] = update.message.text.strip()
    keyboard = [[InlineKeyboardButton("☀️ Утренняя", callback_data="shift:Утренняя")],[InlineKeyboardButton("🌤 Дневная", callback_data="shift:Дневная")],[InlineKeyboardButton("🌙 Вечерняя", callback_data="shift:Вечерняя")]]
    await update.message.reply_text(f"Отлично, *{state['name']}*! Выбери смену:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    return ASK_SHIFT
async def ask_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = get_user_state(user_id)
    state["shift"] = query.data.split(":")[1]
    await query.edit_message_text(f"✅ {state['name']} · {state['shift']} смена\n\nНачинаем чек-лист!", parse_mode="Markdown")
    await context.bot.send_message(chat_id=query.message.chat_id, text=section_text(0, state), parse_mode="Markdown", reply_markup=build_section_keyboard(0, state))
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
        await query.edit_message_text(text=section_text(int(si), state), parse_mode="Markdown", reply_markup=build_section_keyboard(int(si), state))
    elif data.startswith("section:"):
        si = int(data.split(":")[1])
        await query.edit_message_text(text=section_text(si, state), parse_mode="Markdown", reply_markup=build_section_keyboard(si, state))
    elif data == "report":
        report = build_report(state)
        await query.message.reply_text(report, parse_mode="Markdown")
        if MANAGER_CHAT_ID:
            try:
                await context.bot.send_message(chat_id=int(MANAGER_CHAT_ID), text=f"📬 *Отчёт от повара:*\n\n{report}", parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Ошибка: {e}")
    return CHECKLIST
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start(update, context)
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(entry_points=[CommandHandler("start", start)],states={ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],ASK_SHIFT: [CallbackQueryHandler(ask_shift, pattern="^shift:")],CHECKLIST: [CallbackQueryHandler(handle_toggle)]},fallbacks=[CommandHandler("start", start), CommandHandler("reset", reset)])
    app.add_handler(conv)
    app.run_polling()
if __name__ == "__main__":
    main()
