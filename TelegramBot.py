#!/bin/python3

try:
    import telegram
except ModuleNotFoundError:
    print("telegram mudule is not installed")
    print("run command:")
    print("pip3 install python-telegram-bot --upgrade")
    import sys

    sys.exit(1)

from telegram import Update
from telegram.ext import filters, MessageHandler, ApplicationBuilder
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    ConversationHandler,
    CallbackQueryHandler,
)
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    MenuButtonCommands,
)

import sys
import os
import re
import pathlib
import json
from Manager import run_server
from cprint import *


class SimpleGPTbot:
    WAIT_FOR_ROLE = 0x1
    AUTHORIZED_USERS = {
        680657672,  # me
    }

    def __init__(self, token=None):
        if token is None:
            self.token = self.get_token()
        else:
            self.token = token
        self.application = ApplicationBuilder().token(self.token).build()

        start_handler = CommandHandler("start", self.start_command)
        help_handler = CommandHandler("help", self.help_command)
        create_handler = CommandHandler("create", self.create_command)
        delete_handler = CommandHandler("delete", self.delete_command)
        run_handler = CommandHandler("run", self.run_command)
        stop_handler = CommandHandler("stop", self.stop_command)
        cmd_handler = CommandHandler("cmd", self.cmd_command)
        list_handler = CommandHandler("list", self.list_command)
        ps_handler = CommandHandler("ps", self.ps_command)
        list_versions_handler = CommandHandler(
            "list_versions", self.list_versions_command
        )
        update_versions_handler = CommandHandler(
            "update_versions", self.update_versions_command
        )
        echo_handler = MessageHandler(
            filters.TEXT & ~filters.COMMAND, self.echo_handler
        )
        for handler in (
            start_handler,
            help_handler,
            create_handler,
            delete_handler,
            run_handler,
            stop_handler,
            cmd_handler,
            list_handler,
            ps_handler,
            list_versions_handler,
            update_versions_handler,
            echo_handler,
        ):
            self.application.add_handler(handler)

    def start(self):
        self.application.run_polling()

    async def run_request(self, update, context, cmd: str):
        def run_and_capture_output(cmd: str):
            os.system(f"./main.py {cmd} 2>&1 | tee ./log")
            with open("log") as f:
                out = f.read()
            os.system("rm -f ./log")
            return re.sub(r"\x1B\[[0-9;]*[mK]", "", out)

        output = run_and_capture_output(cmd)
        if not pathlib.Path("output.json").exists():
            chat_id = update.effective_chat.id
            text = "INTERNAL ERROR\n" + output
            await context.bot.send_message(chat_id=chat_id, text=text)
            return

        with open("output.json") as j:
            return json.loads(j.read())

    # async def handler(self, update, context):
    #    if await self.prot(update, context):
    #        return

    #    chat_id = update.effective_chat.id
    #    message = update.message.text

    #    output = self.run_and_capture("./main.py " + message)

    #    await context.bot.send_message(
    #        chat_id=chat_id, text=output, disable_web_page_preview=True
    #    )

    async def start_command(self, update, context):
        if await self.prot(update, context):
            return

        chat_id = update.effective_chat.id
        await context.bot.set_chat_menu_button(
            chat_id=chat_id, menu_button=MenuButtonCommands()
        )
        await context.bot.send_message(
            chat_id=chat_id, text="hello, this is minecraft bot, type /help for help"
        )

    async def help_command(self, update, context):
        if await self.prot(update, context):
            return

        chat_id = update.effective_chat.id
        text = (
            "***help***:\n"
            "\n"
            "/start:\n"
            "    _start_ _bot_\n"
            "/help:\n"
            "    _prints_ _this_ _message_\n"
            "/create:\n"
            "    _create_ _new_ _minecraft_ _server_\n"
            "/delete:\n"
            "    _delete_ _minecraft_ _server_\n"
            "/run:\n"
            "    _run_ _minecraft_ _server_\n"
            "/stop:\n"
            "    _stop_ _running_ _minecraft_ _server_\n"
            "/cmd:\n"
            "    _send_ _command_ _to_ _server_ _console_\n"
            "/list:\n"
            "    _list_ _existing_ _minecraft_ _servers_\n"
            "/ps:\n"
            "    _list_ _running_ _minecraft_ _servers_\n"
            "/list_versions\n"
            "    _list_ _avaliable_ _versions_ _to_ _create_ _servers_\n"
            "/update_versions\n"
            "    _update_ _avaliable_ _versions_ _to_ _create_ _server_\n"
            "\n"
            "***\\(c\\) tlucanti***"
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
        )

    async def create_command(self, update, context):
        await self.not_implemented(update, context)

    async def delete_command(self, update, context):
        await self.not_implemented(update, context)

    async def run_command(self, update, context):
        await self.not_implemented(update, context)

    async def stop_command(self, update, context):
        await self.not_implemented(update, context)

    async def cmd_command(self, update, context):
        await self.not_implemented(update, context)

    async def list_command(self, update, context):
        await self.not_implemented(update, context)

    async def ps_command(self, update, context):
        await self.not_implemented(update, context)

    async def list_versions_command(self, update, context):
        resp = await self.run_request(update, context, "list")
        if not resp:
            return

        print(resp)

    async def update_versions_command(self, update, context):
        await self.not_implemented(update, context)

    async def echo_handler(self, update, context):
        if await self.prot(update, context):
            return

        chat_id = update.effective_chat.id
        await context.bot.send_message(
            chat_id=chat_id, text="use /command to run commands"
        )

    async def prot(self, update, context):
        chat_id = update.effective_chat.id
        if chat_id in self.AUTHORIZED_USERS:
            return False

        message = f"you are not authorized to use bot. ID: {chat_id}"
        await context.bot.send_message(chat_id=chat_id, text=message)
        return True

    @staticmethod
    def get_token(path="./.token"):
        try:
            f = open(path, "r")
            token = f.read().strip()
            f.close()
            OK("Telegram token obtained")
            return token
        except FileNotFoundError as e:
            FAIL("place your telegram api token in `.token` file")
            sys.exit(1)

    async def not_implemented(self, update, context):
        if await self.prot(update, context):
            return

        chat_id = update.effective_chat.id
        await context.bot.send_message(chat_id=chat_id, text="not done yet ...")


if __name__ == "__main__":
    bot = SimpleGPTbot()
    bot.start()
