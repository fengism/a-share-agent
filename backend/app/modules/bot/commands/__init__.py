"""Bot 命令处理器。"""

from app.modules.bot.commands.analyze import AnalyzeCommand
from app.modules.bot.commands.base import BotCommand
from app.modules.bot.commands.batch import BatchCommand
from app.modules.bot.commands.chain import ChainCommand
from app.modules.bot.commands.help import HelpCommand
from app.modules.bot.commands.market import MarketCommand
from app.modules.bot.commands.status import StatusCommand
from app.modules.bot.commands.task import TaskCommand

__all__ = [
    "AnalyzeCommand",
    "BatchCommand",
    "ChainCommand",
    "BotCommand",
    "HelpCommand",
    "MarketCommand",
    "StatusCommand",
    "TaskCommand",
]
