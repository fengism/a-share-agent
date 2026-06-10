"""Skill 自然语言描述类。"""

from __future__ import annotations


class Skill:
    """自然语言技能描述，指导 LLM 何时以及如何使用哪些 Tool。

    Param:
        name: 技能唯一标识
        description: 描述该技能的作用和触发场景
        usage: 执行步骤说明，包含每步应使用的工具名称
    """

    def __init__(self, name: str, description: str, usage: str):
        self.name = name
        self.description = description
        self.usage = usage
