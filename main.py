from datetime import datetime
import pytz
import asyncio

import os
from telegram.ext import (Application, CommandHandler, ExtBot, MessageHandler, filters, ConversationHandler, TypeHandler, CallbackQueryHandler, ContextTypes, CallbackContext, PicklePersistence)
from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove,InlineKeyboardButton, InlineKeyboardMarkup, Update)
import logging
from collections import defaultdict
from typing import DefaultDict, Optional, Set
from telegram.constants import ParseMode
import random


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

TOKEN = os.environ['telegram_API_key']
PORT = int(os.environ.get('PORT', 8443))

research_chat_id = -1001856093938
testing_group_id = -829275448

sgTz = pytz.timezone("Asia/Singapore") 

TYPING_REPLY, CONFIRM_MESSAGE,  = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text(
      "Hi! The LKC Medicine Research Bot is ready to serve!\n\n"
      "Send /help for more info on the available commands and resources."
  )

async def ask_question(update, context: ContextTypes.DEFAULT_TYPE):
  reply = await update.message.reply_text(
      "Ok! Fire away! Questions will be sent to the LKC Research Committee and they will get back to you shortly\n\n"
    "You may type /cancel anytime to cancel asking your question."
  )
  
  context.user_data["question_info"] = [reply.id, reply.chat.id]
  context.user_data["question_to_delete"] = {reply.id: reply.chat.id}

  return TYPING_REPLY

async def confirm_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
  reply_keyboard = [
    [InlineKeyboardButton("Confirm", callback_data="confirm"),
     InlineKeyboardButton("Edit", callback_data="edit")]
  ]

  msg = update.message.text
  context.user_data["question"] = msg
  context.user_data["question_to_delete"][update.message.id] = update.message.chat.id

  question_info = context.user_data["question_info"]
  question_message_id = question_info[0]
  question_chat_id = question_info[1]
  
  await context.bot.edit_message_text(
      "Got it! Just to confirm, is this the question that you want to ask?\n\n"
      f"{msg}", message_id = question_message_id, chat_id = question_chat_id,
      reply_markup=InlineKeyboardMarkup(
          reply_keyboard, one_time_keyboard=True
      )
  )

  return CONFIRM_MESSAGE

async def confirmed_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.callback_query.answer()
  
  await update.callback_query.edit_message_text("Ok! Submitting question to the LKC Research Committee...")

  if not "no_of_questions" in context.bot_data:
      context.bot_data["no_of_questions"] = 0
  
  context.bot_data["no_of_questions"] += 1
  no_of_questions = context.bot_data["no_of_questions"]
  
  msg = context.user_data["question"]
  del context.user_data["question"]

  sender = update.callback_query.from_user

  first_name = sender.first_name
  last_name = sender.last_name
  username = sender.username
  user_id = sender.id

  date = datetime.now(sgTz)

  to_send = f"""#{no_of_questions}, {date}

Question by {first_name} {last_name}, @{username}:

{msg}
  """
  reply_keyboard = [
    [InlineKeyboardButton("Reply", callback_data=f"reply {user_id}")]
  ]

  if "follow_up_info" in context.user_data:
    to_send = "[FOLLOW-UP]\n" + to_send
    last_message = context.user_data["last_replied_question"]
    await last_message.reply_text(to_send, reply_markup=InlineKeyboardMarkup(
          reply_keyboard, one_time_keyboard=True
    ))
    del context.user_data["last_replied_question"]
    del context.user_data["follow_up_info"]
  else:
    await context.bot.send_message(research_chat_id, to_send, reply_markup=InlineKeyboardMarkup(
          reply_keyboard, one_time_keyboard=True
      )
    )

  await update.callback_query.message.reply_text(
      "Question successfully submitted!"
  )
  
  for key, val in context.user_data["question_to_delete"].items():
    await delete_message(chat_id = val, message_id = key, time = 0, context = context)
  del context.user_data["question_to_delete"]
  del context.user_data["question_info"]

  return ConversationHandler.END

async def edit_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.callback_query.answer()

  await update.callback_query.edit_message_text(
      "No problem! Just retype your question and resend it!"
  )

  return TYPING_REPLY
  
  
async def cancel_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
  """Cancels and ends the conversation."""
  user = update.message.from_user
  try:
    context.user_data["question_to_delete"][update.message.id] = update.message.chat.id
  except:
    pass
  logger.info("User %s canceled the conversation.", user.first_name)
  cancel_message = await update.message.reply_text(
      "Cancelled. Feel free to continue browsing!")

  question_info = context.user_data["question_info"]
  question_message_id = question_info[0]
  question_chat_id = question_info[1]
   
  try:
    if "follow_up_info" in context.user_data:
      follow_up_info = context.user_data["follow_up_info"]
      reply_keyboard = reply_keyboard = [
        [InlineKeyboardButton("Ask Follow-Up Question", callback_data=f"follow_up {follow_up_info[2]}")]
      ]
      await context.bot.edit_message_text(
        follow_up_info[3], message_id = follow_up_info[0], chat_id = follow_up_info[1],
        reply_markup=InlineKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True
        )
      )
    else:
      await context.bot.edit_message_text(
        "Cancelled.", message_id = question_message_id, chat_id = question_chat_id
      )
      
    for key, val in context.user_data["question_to_delete"].items():
      await delete_message(chat_id = val, message_id = key, time = 0, context = context)
    del context.user_data["question_to_delete"]
    del context.user_data["question_info"]
    del context.user_data["follow_up_info"]
  except:
    pass

  await delete_message(cancel_message.chat.id, cancel_message.id, 1.5, context)

  return ConversationHandler.END

async def follow_up_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
  await update.callback_query.answer()
  replied_question_id = int(update.callback_query.data.split()[1])
  context.user_data["last_replied_question"] = context.bot_data["answered_questions"][replied_question_id][0]

  previous_msg_text = update.callback_query.message.text
  previous_msg_id = update.callback_query.message.message_id
  previous_msg_chat_id = update.callback_query.message.chat.id
  
  context.user_data["follow_up_info"] = [previous_msg_id, previous_msg_chat_id, replied_question_id, previous_msg_text]

  return await ask_question(update.callback_query, context)

async def reply_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
  await update.callback_query.answer()

  if 'in_reply_conversation' in context.user_data:
    if context.user_data['in_reply_conversation']:
      chat = update.callback_query.message.chat
      await chat.send_message("You cannot reply to this message until you have replied to the message that you previously wished to reply to. Otherwise send /cancel to cancel the reply to the previous asker and then press the reply button on this message again.")
      return ConversationHandler.END

  context.user_data['in_reply_conversation'] = True
  
  user_to_reply = int(update.callback_query.data.split()[1])
  previous_msg_text = update.callback_query.message.text
  previous_msg_id = update.callback_query.message.id
  previous_msg_chat_id = update.callback_query.message.chat.id

  context.user_data["reply_info"] = [user_to_reply, previous_msg_text, previous_msg_id, previous_msg_chat_id]
  context.user_data["reply_to_delete"] = {}
  
  new_reply = await update.callback_query.message.reply_text(
      "Alright! Just type down your response and send it!"
  )

  context.user_data["reply_to_delete"][new_reply.message_id] = new_reply.chat.id
  context.user_data["curr_convo"] = [new_reply.message_id, new_reply.chat.id]

  if update.callback_query.data.split()[0] == "edit_response":
    context.user_data["reply_info"].append(int(update.callback_query.data.split()[2]))

  await update.callback_query.message.edit_reply_markup()
  
  return TYPING_REPLY

async def confirm_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
  reply_keyboard = [
    [InlineKeyboardButton("Confirm", callback_data="confirm"),
     InlineKeyboardButton("Edit", callback_data="edit")]
  ]

  msg = update.message.text
  context.user_data["reply_msg"] = msg
  context.user_data["reply_to_delete"][update.message.id] = update.message.chat.id
  
  question_info = context.user_data["curr_convo"]
  question_message_id = question_info[0]
  question_chat_id = question_info[1]
  
  await context.bot.edit_message_text(
      "Got it! Just to confirm, is this the reply that you want to send?\n\n"
      f"{msg}", message_id = question_message_id, chat_id = question_chat_id,
      reply_markup=InlineKeyboardMarkup(
          reply_keyboard, one_time_keyboard=True
      )
  )

  return CONFIRM_MESSAGE

async def confirmed_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.callback_query.answer()
  
  await update.callback_query.edit_message_text("Ok! Sending reply back to user...")

  msg = context.user_data["reply_msg"]

  sender = update.callback_query.from_user

  first_name = sender.first_name
  last_name = sender.last_name
  username = sender.username

  question_info = context.user_data["reply_info"]

  question_user_id = question_info[0]
  complete_question_text = question_info[1]
  question_text = complete_question_text.split("\n\n")[2]
  question_message_id = question_info[2]
  question_chat_id = question_info[3]

  to_send_header = f"""
Reply by {first_name} {last_name}, @{username}:
"""
  to_send_template = f"""
Question:
{question_text}

Reply:"""

  to_send = to_send_header + to_send_template + f"\n{msg}"

  reply_keyboard = [
    [InlineKeyboardButton("Ask Follow-Up Question", callback_data=f"follow_up {question_message_id}")]
  ]
  if len(context.user_data["reply_info"]) > 4:
    question_user_reply_id = question_info[4]
    previous_reply = context.bot_data["replies"][question_user_id][question_user_reply_id] 
    replied = previous_reply[0]
    to_send_header = previous_reply[1]
    to_send_template = previous_reply[2]
    to_send = to_send_header + f"Last Edit by {first_name} {last_name}, @{username}:\n" + to_send_template + f"\n{msg}"
    replied = await replied.edit_text(to_send, reply_markup=InlineKeyboardMarkup(
          reply_keyboard, one_time_keyboard=True
      ))
    await replied.reply_text("This reponse was edited!", quote = True)
  else:
    replied = await context.bot.send_message(question_user_id, to_send, reply_markup=InlineKeyboardMarkup(
          reply_keyboard, one_time_keyboard=True
      ))

  await update.callback_query.edit_message_text(
      "Reply successfully submitted!"
  )

  date = datetime.now(sgTz)
  replied_template = f"""[REPLIED]
{complete_question_text}

Reply by {first_name} {last_name}, @{username} on {date}:
"""
  replied_message = replied_template + f"\n{msg}"

  edit_keyboard = [
    [InlineKeyboardButton("Edit Response", callback_data=f"edit_response {question_user_id} {replied.message_id}")]
  ]
  if len(context.user_data["reply_info"]) > 4:
    replied_template = context.bot_data["answered_questions"][question_message_id][1]
    replied_message = replied_template + f"Last Edit by {first_name} {last_name}, @{username} on {date}:\n" + f"\n{msg}"
    
  message_to_save = await context.bot.edit_message_text(replied_message, message_id = question_message_id, chat_id = question_chat_id, reply_markup=InlineKeyboardMarkup(
          edit_keyboard, one_time_keyboard=True
      ))

  if "answered_questions" not in context.bot_data:
    context.bot_data["answered_questions"] = {}
  if "replies" not in context.bot_data:
    context.bot_data["replies"] = {}
  if question_user_id not in context.bot_data["replies"]:
    context.bot_data["replies"][question_user_id] = {}
  
  context.bot_data["answered_questions"][question_message_id] = [message_to_save, replied_template]
  context.bot_data["replies"][question_user_id][replied.message_id] = [replied, to_send_header, to_send_template]
  
  del context.user_data["reply_msg"]
  del context.user_data["reply_info"]
  del context.user_data["curr_convo"]

  context.user_data['in_reply_conversation'] = False

  for key, val in context.user_data["reply_to_delete"].items():
    await delete_message(chat_id = val, message_id = key, time = 0, context = context)
  del context.user_data["reply_to_delete"]

  return ConversationHandler.END

async def edit_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.callback_query.answer()

  await update.callback_query.edit_message_text(
      "No problem! Just retype your reply and resend it!"
  )

  return TYPING_REPLY
  
  
async def cancel_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
  """Cancels and ends the conversation."""

  user = update.message.from_user
  context.user_data["reply_to_delete"][update.message.id] = update.message.chat.id
  logger.info("User %s canceled the reply.", user.first_name)

  try:
    reset_message_info = context.user_data["reply_info"]
  
    reset_message_user_id = reset_message_info[0]
    reset_message_text = reset_message_info[1]
    reset_message_id = reset_message_info[2]
    reset_message_chat_id = reset_message_info[3]
    if len(context.user_data["reply_info"]) > 4:
      
      reply_keyboard = [
        [InlineKeyboardButton("Edit Response", callback_data=f"edit_response {reset_message_user_id} {reset_message_info[4]}")]
      ]
    else:
      reply_keyboard = [
        [InlineKeyboardButton("Reply", callback_data=f"reply {reset_message_user_id}")]
      ]
    
    await context.bot.edit_message_text(reset_message_text, message_id = reset_message_id, chat_id = reset_message_chat_id, reply_markup=InlineKeyboardMarkup(
          reply_keyboard, one_time_keyboard=True
      )
    )
  except:
    pass
  
  cancel_message = await update.message.reply_text(
      "Cancelled reply!")

  if "reply_msg" in context.user_data:
    del context.user_data["reply_msg"]
  if "reply_info" in context.user_data:
    del context.user_data["reply_info"]
  if "curr_convo" in context.user_data:
    del context.user_data["curr_convo"]
  context.user_data['in_reply_conversation'] = False

  for key, val in context.user_data["reply_to_delete"].items():
    await delete_message(chat_id = val, message_id = key, time = 0, context = context)
  
  await delete_message(cancel_message.chat.id, cancel_message.id, 1.5, context)

  del context.user_data["reply_to_delete"]

  return ConversationHandler.END

async def delete_message(chat_id, message_id, time, context):
  if time > 0:
    await asyncio.sleep(time)
  try:
    await context.bot.delete_message(chat_id = chat_id, message_id = message_id)
  except:
    pass


async def handle_wix_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
  if not "no_of_wix_questions" in context.bot_data:
      context.bot_data["no_of_wix_questions"] = 0
  
  context.bot_data["no_of_wix_questions"] += 1
  no_of_questions = context.bot_data["no_of_wix_questions"]

  sender = update.message.from_user

  full_name = sender.first_name
  email = sender.last_name

  msg = update.message.text

  date = datetime.now(sgTz)
  
  question = f"""
  [WIX] #{no_of_questions}, {date}

Question by {full_name}, {email}:

{msg}
  """
  reply_keyboard = [
    [InlineKeyboardButton("Reply", callback_data=f"replyemail {email}")]
  ]  
  await context.bot.send_message(testing_group_id, question, reply_markup=InlineKeyboardMarkup(
          reply_keyboard, one_time_keyboard=True
      ))

def main() -> None:
    """Run the bot."""

    persistence = PicklePersistence(filepath="conversationbot")
    application = Application.builder().token(TOKEN).persistence(persistence).build()
  
    tele_question = ConversationHandler(
        entry_points=[
          CommandHandler("ask_question", ask_question),
          CallbackQueryHandler(follow_up_question, pattern="^(follow_up)")
        ],
        states={
            TYPING_REPLY: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND), confirm_question
                )
            ],
            CONFIRM_MESSAGE: [
                CallbackQueryHandler(confirmed_question, pattern="^(confirm)$"),
                CallbackQueryHandler(edit_question, pattern="^(edit)$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_question)],
        name="new_question",
        persistent=True,
    )

    tele_reply = ConversationHandler(
        entry_points=[
          CallbackQueryHandler(reply_question, pattern="^(reply)"),
          CallbackQueryHandler(reply_question, pattern="^(edit_response)")
        ],
        states={
            TYPING_REPLY: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND), confirm_reply
                ),
                CallbackQueryHandler(reply_question, pattern="^(reply)")
            ],
            CONFIRM_MESSAGE: [
                CallbackQueryHandler(confirmed_reply, pattern="^(confirm)$"),
                CallbackQueryHandler(edit_reply, pattern="^(edit)$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_reply)],
        name="new_reply",
        persistent=True,
    )
    
    # run track_users in its own group to not interfere with the user handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(
      filters.TEXT & filters.User(username="testemail@e.ntu.edu.sg") & ~(filters.COMMAND), handle_wix_requests
    ))
    application.add_handler(tele_question)
    application.add_handler(tele_reply)
    #application.run_webhook(
    #  listen = "0.0.0.0",
    #  port = PORT,
    #  url_path = TOKEN,
    #  webhook_url = f"https://lkcresearchtest2-matthiasliew.koyeb.app/{TOKEN}"
    #)
    application.run_polling()
    
if __name__ == "__main__":
    main()