"""
数据库迁移脚本：Provider → Platform + PlatformKey

迁移步骤：
1. 创建新表：platforms, platform_keys, platform_key_cooldowns
2. 迁移数据：providers → platforms（按 base_url 去重）
3. 迁移数据：providers → platform_keys
4. 更新 pool_items：provider_id → platform_id
5. 保留旧表用于回滚

回滚步骤：
1. 恢复 pool_items.platform_id → provider_id
2. 删除新表
3. 恢复旧数据
"""
import sqlite3
from datetime import datetime
from typing import List, Dict, Tuple
import sys

def migrate(db_path: str) -> bool:
    """执行迁移"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print(f"开始迁移数据库: {db_path}")

        # ============================================================
        # 1. 创建新表
        # ============================================================

        print("\n[1/6] 创建新表...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS platforms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                base_url TEXT NOT NULL,
                models JSON DEFAULT '[]',
                is_paid INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS platform_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform_id INTEGER NOT NULL,
                api_key TEXT NOT NULL,
                label TEXT DEFAULT '',
                enabled INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (platform_id) REFERENCES platforms(id) ON DELETE CASCADE,
                UNIQUE(platform_id, api_key)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS platform_key_cooldowns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform_key_id INTEGER NOT NULL UNIQUE,
                cooldown_until TEXT NOT NULL,
                strike_count INTEGER DEFAULT 1,
                reason TEXT DEFAULT '',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (platform_key_id) REFERENCES platform_keys(id) ON DELETE CASCADE
            )
        """)

        print("  ✓ 新表创建完成")

        # ============================================================
        # 2. 迁移数据：providers → platforms（按 base_url 去重）
        # ============================================================

        print("\n[2/6] 迁移 providers → platforms...")

        # 查询所有 providers，按 base_url 分组
        cursor.execute("""
            SELECT id, name, base_url, models, is_paid, is_active
            FROM providers
            ORDER BY base_url, id
        """)
        providers = cursor.fetchall()

        # 按 base_url 分组
        base_url_to_platform_id: Dict[str, int] = {}
        base_url_to_providers: Dict[str, List[Tuple]] = {}

        for prov_id, name, base_url, models, is_paid, is_active in providers:
            if base_url not in base_url_to_providers:
                base_url_to_providers[base_url] = []
            base_url_to_providers[base_url].append((prov_id, name, models, is_paid, is_active))

        # 为每个 base_url 创建一个 Platform
        for base_url, provs in base_url_to_providers.items():
            # 使用第一个 provider 的信息作为 Platform 信息
            first_prov = provs[0]
            name = first_prov[1]  # "NVIDIA NIM 1" → "NVIDIA NIM"
            models = first_prov[2]
            is_paid = first_prov[3]
            is_active = first_prov[4]

            # 去掉名称中的编号后缀（如 "NVIDIA NIM 1" → "NVIDIA NIM"）
            if name[-1].isdigit() and name[-2] in (' ', '-', '_'):
                name = name[:-2].strip()

            cursor.execute("""
                INSERT INTO platforms (name, base_url, models, is_paid, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, (name, base_url, str(models), is_paid, is_active))

            platform_id = cursor.lastrowid
            base_url_to_platform_id[base_url] = platform_id

            print(f"  ✓ Platform created: id={platform_id}, name={name}, base_url={base_url}")

        print(f"  ✓ 创建了 {len(base_url_to_platform_id)} 个 Platforms")

        # ============================================================
        # 3. 迁移数据：providers → platform_keys
        # ============================================================

        print("\n[3/6] 迁移 providers → platform_keys...")

        provider_id_to_key_id: Dict[int, int] = {}

        for prov_id, name, base_url, models, is_paid, is_active in providers:
            platform_id = base_url_to_platform_id[base_url]

            # 获取 api_key
            cursor.execute("SELECT api_key FROM providers WHERE id = ?", (prov_id,))
            row = cursor.fetchone()
            if not row:
                continue
            api_key = row[0]

            # label = provider 名称的最后部分（如 "1", "2", "3"）
            label = name.split()[-1] if name.split()[-1].isdigit() else ""

            cursor.execute("""
                INSERT INTO platform_keys (platform_id, api_key, label, enabled, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, (platform_id, api_key, label, is_active, is_active))

            key_id = cursor.lastrowid
            provider_id_to_key_id[prov_id] = key_id

            print(f"  ✓ PlatformKey created: id={key_id}, platform_id={platform_id}, label={label}")

        print(f"  ✓ 创建了 {len(provider_id_to_key_id)} 个 PlatformKeys")

        # ============================================================
        # 4. 更新 pool_items：添加 platform_id, platform_key_id 列
        # ============================================================

        print("\n[4/6] 更新 pool_items 表结构...")

        # 添加新列（如果不存在）
        cursor.execute("PRAGMA table_info(pool_items)")
        columns = [col[1] for col in cursor.fetchall()]

        if "platform_id" not in columns:
            cursor.execute("ALTER TABLE pool_items ADD COLUMN platform_id INTEGER")
            print("  ✓ 添加列: pool_items.platform_id")

        if "platform_key_id" not in columns:
            cursor.execute("ALTER TABLE pool_items ADD COLUMN platform_key_id INTEGER")
            print("  ✓ 添加列: pool_items.platform_key_id")

        # ============================================================
        # 5. 更新 pool_items 数据：provider_id → platform_id
        # ============================================================

        print("\n[5/6] 更新 pool_items 数据映射...")

        cursor.execute("""
            SELECT id, provider_id, model, priority
            FROM pool_items
            WHERE provider_id IS NOT NULL
        """)
        pool_items = cursor.fetchall()

        for pi_id, provider_id, model, priority in pool_items:
            if provider_id not in provider_id_to_key_id:
                print(f"  ⚠ 跳过 pool_item {pi_id}: provider_id {provider_id} 未找到对应的 platform_key")
                continue

            # 查找 platform_id
            cursor.execute("SELECT base_url FROM providers WHERE id = ?", (provider_id,))
            row = cursor.fetchone()
            if not row:
                continue
            base_url = row[0]
            platform_id = base_url_to_platform_id.get(base_url)

            if platform_id is None:
                print(f"  ⚠ 跳过 pool_item {pi_id}: 未找到对应的 platform")
                continue

            cursor.execute("""
                UPDATE pool_items
                SET platform_id = ?, platform_key_id = ?
                WHERE id = ?
            """, (platform_id, provider_id_to_key_id[provider_id], pi_id))

        print(f"  ✓ 更新了 {len(pool_items)} 个 pool_items")

        # ============================================================
        # 6. 提交
        # ============================================================

        print("\n[6/6] 提交迁移...")
        conn.commit()
        print("  ✓ 迁移完成！")

        # ============================================================
        # 验证
        # ============================================================

        print("\n=== 验证迁移结果 ===")
        cursor.execute("SELECT COUNT(*) FROM platforms")
        print(f"Platforms: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM platform_keys")
        print(f"PlatformKeys: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM pool_items WHERE platform_id IS NOT NULL")
        print(f"PoolItems (with platform_id): {cursor.fetchone()[0]}")

        return True

    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


def rollback(db_path: str) -> bool:
    """回滚迁移"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print(f"\n开始回滚数据库: {db_path}")

        # 删除新列
        cursor.execute("PRAGMA table_info(pool_items)")
        columns = [col[1] for col in cursor.fetchall()]

        if "platform_id" in columns:
            cursor.execute("ALTER TABLE pool_items DROP COLUMN platform_id")
            print("  ✓ 删除列: pool_items.platform_id")

        if "platform_key_id" in columns:
            cursor.execute("ALTER TABLE pool_items DROP COLUMN platform_key_id")
            print("  ✓ 删除列: pool_items.platform_key_id")

        # 删除新表
        cursor.execute("DROP TABLE IF EXISTS platform_key_cooldowns")
        print("  ✓ 删除表: platform_key_cooldowns")

        cursor.execute("DROP TABLE IF EXISTS platform_keys")
        print("  ✓ 删除表: platform_keys")

        cursor.execute("DROP TABLE IF EXISTS platforms")
        print("  ✓ 删除表: platforms")

        conn.commit()
        print("  ✓ 回滚完成！")
        return True

    except Exception as e:
        print(f"\n❌ 回滚失败: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    db_path = sys.argv[1] if len(sys.argv) > 1 else "/root/data/ai_gateway.db"

    if "--rollback" in sys.argv:
        success = rollback(db_path)
    else:
        success = migrate(db_path)

    sys.exit(0 if success else 1)