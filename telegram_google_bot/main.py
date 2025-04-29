
import telebot
import gspread
from google.oauth2.service_account import Credentials
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Bot token va Sheets ulanishi
BOT_TOKEN = "8065008364:AAFldtENU_IK_cnluZags-uRRAX0OyOFyEI"
SPREADSHEET_ID = "1fo45h5wMil_t3t0TKlZbA5J1iGwcVTISqanI67LbxVY"

bot = telebot.TeleBot(BOT_TOKEN)

# Foydalanuvchi tanlovi (kengaytirilgan)
user_data = {}

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(SPREADSHEET_ID)

# Maxsus uzun ro'yxatli varaqlar
SPECIAL_SHEETS = ["G'alla pudratchilari (kontur kesimida)", "Paxta pudratchilari (kontur kesimida)"]

# Foydalanuvchi ma'lumotlari
user_data = {}

# /start komandasi
@bot.message_handler(commands=["start"])
def start_handler(message):
    user_data.pop(message.chat.id, None)  # Har doim yangilanishi uchun
    sheet = spreadsheet.worksheets()[0]
    data = sheet.get_all_values()
    header = data[0]

    hudud_index = header.index("Hudud") if "Hudud" in header else header.index("Ҳудудлар номи")
    hududlar = sorted(set(row[hudud_index] for row in data[1:] if row[hudud_index]))

    markup = InlineKeyboardMarkup(row_width=2)
    for hudud in hududlar:
        markup.add(InlineKeyboardButton(hudud, callback_data=f"region:{hudud}"))

    bot.send_message(message.chat.id, "📍 *Quyidagi hududlardan birini tanlang:*", parse_mode="Markdown", reply_markup=markup)

# Callback handler
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id

    if call.data.startswith("region:"):
        selected_hudud = call.data.split("region:")[1]
        user_data[chat_id] = {"hudud": selected_hudud}

        markup = InlineKeyboardMarkup(row_width=2)
        for sheet in spreadsheet.worksheets():
            markup.add(InlineKeyboardButton(sheet.title, callback_data=f"section:{sheet.title}"))

        markup.add(
            InlineKeyboardButton("🔙 Orqaga", callback_data="home")
        )
        bot.edit_message_text(
            f"🔎 *{selected_hudud}* hududi tanlandi.\n\n🗂 Endi bo‘limni tanlang:",
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif call.data.startswith("section:"):
        section = call.data.split("section:")[1]
        selected_hudud = user_data.get(chat_id, {}).get("hudud", "")
        user_data[chat_id]["section"] = section

        if section in SPECIAL_SHEETS:
            # Maxsus bo'lim sahifalash
            handle_special_list(call.message, section, selected_hudud, page=1)
        else:
            # Oddiy bo'lim
            send_section_data(call.message, section, selected_hudud)


    elif call.data.startswith("page:"):
        _, section, selected_hudud, page = call.data.split(":")
        handle_special_list(call.message, section, selected_hudud, int(page))

    elif call.data.startswith("select:"):
        _, section, selected_hudud, index = call.data.split(":")
        show_selected_row(call.message, section, selected_hudud, int(index))

    elif call.data == "home":
        start_handler(call.message)


# Maxsus varaqlar uchun ro'yxat
# Maxsus varaqlar uchun ro'yxat
def handle_special_list(message, section, selected_hudud, page):
    sheet = spreadsheet.worksheet(section)
    data = sheet.get_all_values()
    header = data[0]
    rows = data[1:]
    contractor_index = 1  # Pudratchi familiyasi 2-ustunda

    contractors = []
    current_region = ""
    for row in rows:
        if row[0]:
            current_region = row[0]
        if current_region == selected_hudud:
            if len(row) > contractor_index:
                contractors.append(row)

    if not contractors:
        bot.edit_message_text(f"🔍 *{selected_hudud}* uchun '{section}' bo‘limida ma’lumot topilmadi.",
                              chat_id=message.chat.id, message_id=message.message_id, parse_mode="Markdown")
        return

    per_page = 10
    start = (page - 1) * per_page
    end = start + per_page
    page_contractors = contractors[start:end]

    javob = f"📍 *{selected_hudud}* uchun pudratchilar ro'yxati (sahifa {page}):\n\n"
    for idx, row in enumerate(page_contractors, start=start + 1):
        familiya = row[contractor_index] if len(row) > contractor_index else ""
        javob += f"{idx}. {familiya}\n"

    markup = InlineKeyboardMarkup(row_width=5)
    buttons = []

    for idx in range(start + 1, min(end, len(contractors)) + 1):
        buttons.append(InlineKeyboardButton(str(idx), callback_data=f"select:{section}:{selected_hudud}:{idx - 1}"))

    # 5ta ustun qilib joylaymiz
    for i in range(0, len(buttons), 5):
        markup.row(*buttons[i:i + 5])

    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton("⬅️ Orqaga", callback_data=f"page:{section}:{selected_hudud}:{page - 1}"))
    if end < len(contractors):
        nav_buttons.append(
            InlineKeyboardButton("➡️ Oldinga", callback_data=f"page:{section}:{selected_hudud}:{page + 1}"))

    if nav_buttons:
        markup.add(*nav_buttons)

    markup.add(
        InlineKeyboardButton("🔙 Orqaga", callback_data=f"region:{selected_hudud}"),
        InlineKeyboardButton("🏠 Bosh sahifa", callback_data="home")
    )

    bot.edit_message_text(javob, chat_id=message.chat.id, message_id=message.message_id, reply_markup=markup,
                          parse_mode="Markdown")
    user_data[message.chat.id]["contractors"] = contractors

# Tanlangan pudratchi ma'lumotlarini ko'rsatish
def show_selected_row(message, section, selected_hudud, index):
    contractors = user_data.get(message.chat.id, {}).get("contractors", [])
    if index < 0 or index >= len(contractors):
        bot.send_message(message.chat.id, "Xatolik yuz berdi.")
        return

    sheet = spreadsheet.worksheet(section)
    header = sheet.get_all_values()[0]
    row = contractors[index]

    javob = f"📍 *{selected_hudud}* uchun tanlangan pudratchi ma'lumotlari:\n\n"
    for key, value in zip(header, row):
        if value.strip():
            javob += f"*{key}*: {value}\n"

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔙 Orqaga", callback_data=f"section:{section}"),
        InlineKeyboardButton("🏠 Bosh sahifa", callback_data="home")
    )

    bot.edit_message_text(javob, chat_id=message.chat.id, message_id=message.message_id, reply_markup=markup, parse_mode="Markdown")

# Oddiy varaqlar uchun ma'lumot chiqarish
def send_section_data(message, section, selected_hudud):
    sheet = spreadsheet.worksheet(section)
    data = sheet.get_all_values()
    header = data[0]
    rows = data[1:]

    javob = f"📍 *{selected_hudud}* uchun *{section}* bo‘limidagi ma’lumotlar:\n\n"
    found = False
    current_region = ""

    for row in rows:
        if row[0]:
            current_region = row[0]
        if current_region == selected_hudud:
            found = True
            for key, value in zip(header, row):
                if value.strip():
                    javob += f"*{key}*: {value}\n"
            javob += "\n"

    if not found:
        javob = f"🔍 *{selected_hudud}* uchun '{section}' bo‘limida ma’lumot topilmadi."

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔙 Orqaga", callback_data=f"region:{selected_hudud}"),
        InlineKeyboardButton("🏠 Bosh sahifa", callback_data="home")
    )

    bot.edit_message_text(javob, chat_id=message.chat.id, message_id=message.message_id, reply_markup=markup, parse_mode="Markdown")

# Kontur raqami bo'yicha qidirish
@bot.message_handler(func=lambda message: True)
def text_handler(message):
    chat_id = message.chat.id
    data = user_data.get(chat_id)
    if not data or "section" not in data or data["section"] not in SPECIAL_SHEETS:
        return

    section = data["section"]
    selected_hudud = data["hudud"]
    kontur = message.text.strip()

    sheet = spreadsheet.worksheet(section)
    all_data = sheet.get_all_values()
    header = all_data[0]
    rows = all_data[1:]

    kontur_index = 2  # 3-ustun

    javob = f"📍 *{selected_hudud}* uchun kontur raqamiga mos ma'lumot:\n\n"
    found = False
    current_region = ""

    for row in rows:
        if row[0]:
            current_region = row[0]
        if current_region == selected_hudud and len(row) > kontur_index and row[kontur_index] == kontur:
            found = True
            for key, value in zip(header, row):
                if value.strip():
                    javob += f"*{key}*: {value}\n"
            break

    if not found:
        javob = f"🔍 Kontur raqami *{kontur}* bo‘yicha ma’lumot topilmadi."

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔙 Orqaga", callback_data=f"section:{section}"),
        InlineKeyboardButton("🏠 Bosh sahifa", callback_data="home")
    )
    bot.send_message(chat_id, javob, parse_mode="Markdown", reply_markup=markup)

# Botni ishga tushirish
print("Bot ishga tushdi...")
bot.infinity_polling()
