#!/usr/bin/env python3
"""
管理员密码重置与账号救援命令行脚本。

仅更新指定的已有账号，保留 UID 与 AI 配置；账号不存在时直接报错，不创建或替换账号。

用法:
    python backend/scripts/reset_admin_password.py [username] [--password NEW_PASSWORD] [--admin]

示例:
    # 1. 为 admin 随机生成一个强密码并重置：
    python backend/scripts/reset_admin_password.py admin

    # 2. 为 admin 设置指定新密码：
    python backend/scripts/reset_admin_password.py admin --password MyStrongPass123

    # 3. 将某指定用户设置为管理员并重置密码：
    python backend/scripts/reset_admin_password.py my_user --password MyStrongPass123 --admin
"""

import argparse
import sys
from pathlib import Path


def main() -> int:
    # 直接运行脚本时先加入 backend 路径，再导入应用模块。
    backend_dir = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(backend_dir))
    from app.core.security import generate_temp_password
    from app.infrastructure.persistence import account_store
    from app.modules.auth.schemas import validate_password_strength

    parser = argparse.ArgumentParser(description="Trade-Agent 管理员密码重置与账号救援工具")
    parser.add_argument(
        "username",
        nargs="?",
        default="admin",
        help="待重置密码的管理员用户名（默认为 admin）",
    )
    parser.add_argument(
        "--password",
        "-p",
        default="",
        help="指定新密码。如果未提供，系统将自动生成随机安全密码并在终端打印",
    )
    parser.add_argument(
        "--admin",
        action="store_true",
        default=False,
        help="强制将该用户提升为管理员身份",
    )

    args = parser.parse_args()
    username = (args.username or "").strip()

    admins = [u for u in account_store.list_users() if u.get("is_admin")]

    # 只处理指定的已有账号，禁止自动替换目标或创建新账号。
    user = account_store.get_user_by_username(username)
    if not user:
        print(f"\n[错误] 用户 '{username}' 不存在！", file=sys.stderr)
        if admins:
            print("系统当前存在的管理员账号如下：", file=sys.stderr)
            for a in admins:
                status = "正常" if a.get("is_active", 1) else "已禁用"
                print(f"  - 用户名: {a['username']} (ID: {a['id']}, 状态: {status})", file=sys.stderr)
            print("\n请指定正确的用户名重置，例如: python scripts/reset_admin_password.py <用户名>", file=sys.stderr)
        else:
            print("系统目前没有任何管理员；本脚本不会创建账号，请核对数据库与用户名。", file=sys.stderr)
        return 1

    # 确定新密码
    if args.password:
        new_password = args.password.strip()
        try:
            validate_password_strength(new_password)
        except ValueError as e:
            print(f"\n[错误] 密码不符合安全规范: {e}", file=sys.stderr)
            return 1
    else:
        new_password = generate_temp_password()

    # 执行重置
    success = account_store.reset_password_direct(
        username=username,
        new_password=new_password,
        ensure_admin=args.admin or bool(user.get("is_admin")),
        ensure_active=True,
    )

    if not success:
        print("\n[错误] 密码重置失败，请检查数据库连接与权限。", file=sys.stderr)
        return 1

    print("=" * 60)
    print("✅ 管理员密码重置成功！")
    print(f"  用户名:    {username}")
    print(f"  用户 UID: {user['id']}（保持不变）")
    print(f"  新密码:    {new_password}")
    print("  账号状态:  正常 (已解除禁用/已激活)")
    print(
        "  安全说明:  该账号在所有设备上的旧登录凭据已失效，请使用新密码重新登录；UID、AI 配置、聊天记录和业务数据不受影响。"
    )
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
