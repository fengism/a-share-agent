"""One-shot account reset.

Wipes all account data (users / sessions / invites / per-user config / reset
tokens / Bot jobs / Bot rate limits) so the next registration becomes the first-user admin again
— without a new invite code. Other application data (market cache, etc.) is
left untouched.

Usage (from backend/):
    uv run python -m app.scripts.reset_accounts            # interactive confirm
    uv run python -m app.scripts.reset_accounts --yes      # skip confirmation
    uv run python -m app.scripts.reset_accounts --stats    # only show counts

Docker:
    docker compose exec backend python -m app.scripts.reset_accounts --yes

Stop (or restart after) the backend so no stale in-memory session is reused.
"""
import argparse

from app.infrastructure.persistence import account_store, init_db


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="清空账号数据（users / 会话 / 邀请 / 配置 / 重置令牌 / Bot 任务与限流）。不影响行情缓存。",
    )
    parser.add_argument("-y", "--yes", action="store_true", help="跳过确认直接执行（非交互 / 脚本用）")
    parser.add_argument("--stats", action="store_true", help="只显示各表当前条数，不删除")
    args = parser.parse_args(argv)

    init_db()  # ensure the account tables exist before counting
    counts = account_store.count_all_accounts()

    print("当前账号数据：")
    for table, n in counts.items():
        print(f"  {table:16} {n}")

    if args.stats:
        return 0

    if all(v == 0 for v in counts.values()):
        print("账号表已为空，无需重置。")
        return 0

    if not args.yes:
        print("\n⚠️  这将永久删除以上全部账号数据（不影响行情缓存等其它数据，且不可撤销）。")
        try:
            reply = input("确认清空？输入 yes 继续：").strip().lower()
        except EOFError:
            reply = ""
        if reply != "yes":
            print("已取消。")
            return 1

    before = account_store.reset_all_accounts()
    print(
        "\n✅ 已清空："
        f"users={before.get('users', 0)}、"
        f"auth_sessions={before.get('auth_sessions', 0)}、"
        f"invites={before.get('invites', 0)}、"
        f"user_config={before.get('user_config', 0)}、"
        f"password_resets={before.get('password_resets', 0)}、"
        f"bot_command_jobs={before.get('bot_command_jobs', 0)}、"
        f"bot_rate_limit_events={before.get('bot_rate_limit_events', 0)}。"
    )
    print("下一步：重启后端 → 打开注册页（needs-setup 现在为 true）→ 首个注册账号即管理员（免邀请码）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
