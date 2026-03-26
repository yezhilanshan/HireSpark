#!/usr/bin/env python3
"""
数据库维护脚本 - 自动执行数据库维护任务

功能：
1. 备份数据库
2. 清理旧数据
3. 优化数据库（VACUUM）
4. 生成统计报告

使用方法：
    python maintenance.py --backup           # 仅备份
    python maintenance.py --cleanup          # 仅清理（默认30天）
    python maintenance.py --cleanup --days 60  # 清理60天前数据
    python maintenance.py --vacuum           # 仅优化
    python maintenance.py --all              # 执行所有维护任务
    python maintenance.py --report           # 生成统计报告
"""

import sys
import os
import argparse
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import DatabaseManager


class MaintenanceManager:
    """数据库维护管理器"""
    
    def __init__(self, db_path='interview_system.db'):
        """初始化维护管理器"""
        self.db = DatabaseManager(db_path)
        self.log_messages = []
    
    def log(self, message):
        """记录日志消息"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        self.log_messages.append(log_msg)
    
    def backup(self):
        """执行数据库备份"""
        self.log("=" * 60)
        self.log("开始备份数据库...")
        
        result = self.db.backup_database()
        
        if result['success']:
            self.log(f"✓ 备份成功: {result['backup_path']}")
            return True
        else:
            self.log(f"✗ 备份失败: {result.get('error', 'Unknown error')}")
            return False
    
    def cleanup(self, days=30):
        """清理旧数据"""
        self.log("=" * 60)
        self.log(f"开始清理 {days} 天前的数据...")
        
        result = self.db.cleanup_old_data(days=days)
        
        if result['success']:
            deleted_count = result['deleted_count']
            if deleted_count > 0:
                self.log(f"✓ 成功删除 {deleted_count} 条旧记录")
            else:
                self.log("✓ 没有需要清理的旧数据")
            return True
        else:
            self.log(f"✗ 清理失败: {result.get('error', 'Unknown error')}")
            return False
    
    def vacuum(self):
        """优化数据库"""
        self.log("=" * 60)
        self.log("开始优化数据库（VACUUM）...")
        
        # 获取优化前的数据库大小
        size_before = self.db.get_database_size()
        
        result = self.db.vacuum_database()
        
        if result['success']:
            # 获取优化后的数据库大小
            size_after = self.db.get_database_size()
            
            self.log(f"✓ 优化完成")
            self.log(f"  优化前: {size_before['size_mb']} MB")
            self.log(f"  优化后: {size_after['size_mb']} MB")
            
            saved = size_before['size_mb'] - size_after['size_mb']
            if saved > 0:
                self.log(f"  节省空间: {saved:.2f} MB")
            
            return True
        else:
            self.log(f"✗ 优化失败: {result.get('error', 'Unknown error')}")
            return False
    
    def generate_report(self):
        """生成统计报告"""
        self.log("=" * 60)
        self.log("生成统计报告...")
        
        try:
            # 获取数据库大小
            size_info = self.db.get_database_size()
            
            # 获取统计摘要
            summary = self.db.get_statistics_summary()
            
            # 获取风险分布
            risk_dist = self.db.get_risk_level_distribution()
            
            # 获取事件类型分布
            event_dist = self.db.get_event_type_distribution()
            
            # 输出报告
            self.log("")
            self.log("【数据库状态】")
            self.log(f"  文件大小: {size_info['size_mb']} MB")
            self.log("")
            
            self.log("【统计摘要】")
            self.log(f"  总面试数: {summary['total_interviews']}")
            self.log(f"  平均最高作弊概率: {summary['avg_max_probability']:.2f}%")
            self.log(f"  总事件数: {summary['total_events']}")
            self.log(f"  平均面试时长: {summary['avg_duration']:.1f} 秒")
            self.log("")
            
            self.log("【风险等级分布】")
            self.log(f"  低风险 (LOW):    {risk_dist['LOW']} 个")
            self.log(f"  中风险 (MEDIUM): {risk_dist['MEDIUM']} 个")
            self.log(f"  高风险 (HIGH):   {risk_dist['HIGH']} 个")
            self.log("")
            
            if event_dist:
                self.log("【事件类型分布】")
                for event_type, count in event_dist.items():
                    self.log(f"  {event_type}: {count} 次")
            
            return True
            
        except Exception as e:
            self.log(f"✗ 生成报告失败: {str(e)}")
            return False
    
    def run_all(self, cleanup_days=30):
        """执行所有维护任务"""
        self.log("=" * 60)
        self.log("开始执行完整维护流程")
        self.log("=" * 60)
        
        success = True
        
        # 1. 备份
        if not self.backup():
            success = False
        
        # 2. 清理
        if not self.cleanup(days=cleanup_days):
            success = False
        
        # 3. 优化
        if not self.vacuum():
            success = False
        
        # 4. 报告
        if not self.generate_report():
            success = False
        
        self.log("=" * 60)
        if success:
            self.log("✓ 所有维护任务完成")
        else:
            self.log("⚠ 部分维护任务失败，请检查日志")
        self.log("=" * 60)
        
        return success
    
    def save_log(self, log_file='logs/maintenance.log'):
        """保存日志到文件"""
        try:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            with open(log_file, 'a', encoding='utf-8') as f:
                for msg in self.log_messages:
                    f.write(msg + '\n')
                f.write('\n')
            
            print(f"\n日志已保存至: {log_file}")
            
        except Exception as e:
            print(f"保存日志失败: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='数据库维护脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python maintenance.py --backup           # 仅备份数据库
  python maintenance.py --cleanup          # 清理30天前的数据
  python maintenance.py --cleanup --days 60  # 清理60天前的数据
  python maintenance.py --vacuum           # 优化数据库
  python maintenance.py --report           # 生成统计报告
  python maintenance.py --all              # 执行所有维护任务
        """
    )
    
    parser.add_argument(
        '--db',
        default='interview_system.db',
        help='数据库文件路径 (默认: interview_system.db)'
    )
    
    parser.add_argument(
        '--backup',
        action='store_true',
        help='备份数据库'
    )
    
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='清理旧数据'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='清理多少天前的数据 (默认: 30)'
    )
    
    parser.add_argument(
        '--vacuum',
        action='store_true',
        help='优化数据库（VACUUM）'
    )
    
    parser.add_argument(
        '--report',
        action='store_true',
        help='生成统计报告'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='执行所有维护任务'
    )
    
    parser.add_argument(
        '--log',
        default='logs/maintenance.log',
        help='日志文件路径 (默认: logs/maintenance.log)'
    )
    
    args = parser.parse_args()
    
    # 检查是否至少指定了一个操作
    if not any([args.backup, args.cleanup, args.vacuum, args.report, args.all]):
        parser.print_help()
        print("\n错误: 请至少指定一个操作 (--backup, --cleanup, --vacuum, --report, --all)")
        sys.exit(1)
    
    # 初始化维护管理器
    maintenance = MaintenanceManager(args.db)
    
    try:
        if args.all:
            # 执行所有维护任务
            maintenance.run_all(cleanup_days=args.days)
        else:
            # 按指定顺序执行各个任务
            if args.backup:
                maintenance.backup()
            
            if args.cleanup:
                maintenance.cleanup(days=args.days)
            
            if args.vacuum:
                maintenance.vacuum()
            
            if args.report:
                maintenance.generate_report()
        
        # 保存日志
        maintenance.save_log(args.log)
        
    except KeyboardInterrupt:
        print("\n\n维护任务已被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n错误: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
