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
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
import random


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

api_key = os.environ['telegram_API_key']

research_chat_id = -1001856093938

sgTz = pytz.timezone("Asia/Singapore") 

TYPING_REPLY, CONFIRM_MESSAGE,  = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text(
      "Hi! The LKC Medicine Research Bot is ready to serve!\n\n"
      "Send /help for more info on the available commands and resources."
  )

async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
  reply = await update.message.reply_text(
      "Ok! Fire away! Questions will be sent to the LKC Research Committee and they will get back to you shortly\n\n"
    "You may type /cancel anytime to cancel asking your question."
  )
  
  context.user_data["question_info"] = [reply.id, reply.chat.id]
  context.user_data["question_to_delete"] = {}

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

  to_send = f"""
  #{no_of_questions}, {date}

Question by {first_name} {last_name}, @{username}:

{msg}
  """
  reply_keyboard = [
    [InlineKeyboardButton("Reply", callback_data=f"reply {user_id}")]
  ]
  
  await context.bot.send_message(research_chat_id, to_send, reply_markup=InlineKeyboardMarkup(
          reply_keyboard, one_time_keyboard=True
    )
  )

  await update.callback_query.edit_message_text(
      "Question successfully submitted!"
  )
  
  for key, val in context.user_data["question_to_delete"].items():
    await delete_message(chat_id = val, message_id = key, time = 0, context = context)
  del context.user_data["question_to_delete"]

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
  context.user_data["question_to_delete"][update.message.id] = update.message.chat.id
  logger.info("User %s canceled the conversation.", user.first_name)
  cancel_message = await update.message.reply_text(
      "Cancelled. Feel free to continue browsing!")

  for key, val in context.user_data["question_to_delete"].items():
      await delete_message(chat_id = val, message_id = key, time = 0, context = context)
  del context.user_data["question_to_delete"]

  await delete_message(cancel_message.chat.id, cancel_message.id, 1.5, context)

  return ConversationHandler.END



async def reply_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
  await update.callback_query.answer()

  if 'in_reply_conversation' in context.user_data:
    if context.user_data['in_reply_conversation']:
      chat = update.callback_query.message.chat
      await chat.send_message("You cannot reply to this message until you have replied to the message that you previously wished to reply to. Otherwise send /cancel to cancel the reply to the previous asker and then press the reply button on this message again.")
      return TYPING_REPLY

  context.user_data['in_reply_conversation'] = True
  
  user_to_reply = update.callback_query.data.split()[1]
  previous_msg_text = update.callback_query.message.text
  previous_msg_id = update.callback_query.message.id
  previous_msg_chat_id = update.callback_query.message.chat.id

  context.user_data["reply_info"] = [user_to_reply, previous_msg_text, previous_msg_id, previous_msg_chat_id]
  context.user_data["reply_to_delete"] = {}
  
  await update.callback_query.edit_message_text(
      "Alright! Just type down your response and send it!"
  )

  return TYPING_REPLY

async def confirm_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
  reply_keyboard = [
    [InlineKeyboardButton("Confirm", callback_data="confirm"),
     InlineKeyboardButton("Edit", callback_data="edit")]
  ]

  msg = update.message.text
  context.user_data["reply_msg"] = msg
  context.user_data["reply_to_delete"][update.message.id] = update.message.chat.id
  
  question_info = context.user_data["reply_info"]
  question_message_id = question_info[2]
  question_chat_id = question_info[3]
  
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

  to_send = f"""
Reply by {first_name} {last_name}, @{username}:

Question:
{question_text}

Reply:
{msg}
  """
  
  await context.bot.send_message(question_user_id, to_send)

  await update.callback_query.edit_message_text(
      "Reply successfully submitted!"
  )

  date = datetime.now(sgTz)
  replied_message = f"""[REPLIED]
{complete_question_text}

Reply by {first_name} {last_name}, @{username} on {date}:
{msg}
"""

  await context.bot.edit_message_text(replied_message, message_id = question_message_id, chat_id = question_chat_id)
  
  del context.user_data["reply_msg"]
  del context.user_data["reply_info"]

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

async def main() -> None:
    """Run the bot."""

    persistence = PicklePersistence(filepath="conversationbot")
    application = Application.builder().token(api_key).persistence(persistence).build()
    
    async def telegram(request: Request) -> Response:
        """Handle incoming Telegram updates by putting them into the `update_queue`"""
        await application.update_queue.put(
            Update.de_json(data=await request.json(), bot=application.bot)
        )
        return Response()
    starlette_app = Starlette(
            routes=[
                Route("/telegram", telegram, methods=["POST"])
            ]
        )
      
    webserver = uvicorn.Server(
            config=uvicorn.Config(
                app=starlette_app,
                port=os.environ['PORT'] or 17995,
                use_colors=False,
                host="0.0.0.0",
            )
        )  
    new_question = ConversationHandler(
        entry_points=[CommandHandler("ask_question", ask_question)],
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

    new_reply = ConversationHandler(
        entry_points=[CallbackQueryHandler(reply_question, pattern="^(reply)")],
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
    application.add_handler(new_question)
    application.add_handler(new_reply)
    await application.bot.set_webhook(url = "https://lkc-med-telegram-bot.herokuapp.com/telegram")

    
  
    async with application:
        await application.start()
        await webserver.serve()
        await application.stop()
  
  


if __name__ == "__main__":
    asyncio.run(main())