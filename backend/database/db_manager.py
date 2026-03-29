"""
数据库管理器 - 负责所有数据持久化操作

改进内容：
- 添加连接上下文管理器，确保连接正确关闭
- 添加事务支持，提高并发安全性
- 添加数据库备份和恢复功能
- 添加数据清理和归档功能
- 优化查询性能
"""
import sqlite3
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager
from threading import Lock
import os


class DatabaseManager:
    """数据库管理器 - 处理面试数据的持久化存储"""
    
    def __init__(self, db_path='interview_system.db'):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._lock = Lock()  # 线程锁，保证并发安全
        self.init_database()
    
    def init_database(self):
        """初始化数据库表结构"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 面试记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interview_id TEXT UNIQUE NOT NULL,
                    start_time DATETIME,
                    end_time DATETIME,
                    duration INTEGER,
                    max_probability REAL,
                    avg_probability REAL,
                    risk_level TEXT,
                    events_count INTEGER,
                    report_path TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 事件记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interview_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    score INTEGER DEFAULT 0,
                    description TEXT,
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
                )
            ''')
            
            # 创建索引加速查询
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_events_interview_id 
                ON events(interview_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_events_type 
                ON events(event_type)
            ''')
            
            # 统计表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interview_id TEXT UNIQUE NOT NULL,
                    total_deviations INTEGER DEFAULT 0,
                    total_mouth_open INTEGER DEFAULT 0,
                    total_multi_person INTEGER DEFAULT 0,
                    off_screen_ratio REAL DEFAULT 0,
                    frames_processed INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
                )
            ''')

            # 简历信息表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS resumes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    file_hash TEXT,
                    parsed_data TEXT,
                    projects TEXT,
                    experiences TEXT,
                    education TEXT,
                    skills TEXT,
                    status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建索引加速查询
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_resumes_user_id
                ON resumes(user_id)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_resumes_status
                ON resumes(status)
            ''')

            # 面试轮次配置表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interview_rounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    round_type TEXT NOT NULL,  -- 'technical', 'project', 'system_design', 'hr'
                    position TEXT NOT NULL,
                    difficulty TEXT,
                    questions TEXT,  -- JSON 数组
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建索引加速查询
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interview_rounds_type
                ON interview_rounds(round_type)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interview_rounds_position
                ON interview_rounds(position)
            ''')

            # 面试对话历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interview_dialogues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interview_id TEXT NOT NULL,
                    round_type TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT,
                    llm_feedback TEXT,
                    score INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interview_dialogues_interview_id
                ON interview_dialogues(interview_id)
            ''')

            # 语音表达评估明细表（整题终稿 + 对齐后指标）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS speech_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interview_id TEXT NOT NULL,
                    turn_id TEXT NOT NULL,
                    answer_session_id TEXT,
                    round_type TEXT,
                    final_transcript TEXT,
                    word_timestamps_json TEXT,
                    pause_events_json TEXT,
                    filler_events_json TEXT,
                    speech_metrics_final_json TEXT,
                    realtime_metrics_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(interview_id, turn_id),
                    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_speech_evaluations_interview_id
                ON speech_evaluations(interview_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_speech_evaluations_created_at
                ON speech_evaluations(created_at)
            ''')

            # 三层评价结果表（支持版本化、幂等与聚合统计）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interview_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interview_id TEXT NOT NULL,
                    turn_id TEXT NOT NULL,
                    question_id TEXT,
                    user_id TEXT,
                    round_type TEXT NOT NULL,
                    position TEXT,
                    question TEXT,
                    answer TEXT,
                    evaluation_version TEXT NOT NULL DEFAULT 'v1',
                    rubric_version TEXT NOT NULL DEFAULT 'unknown',
                    prompt_version TEXT NOT NULL DEFAULT 'v1',
                    llm_model TEXT NOT NULL DEFAULT '',
                    eval_task_key TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    layer1_json TEXT,
                    layer2_json TEXT,
                    rubric_level TEXT,
                    overall_score REAL,
                    confidence REAL,
                    technical_accuracy_score REAL,
                    knowledge_depth_score REAL,
                    completeness_score REAL,
                    logic_score REAL,
                    job_match_score REAL,
                    authenticity_score REAL,
                    ownership_score REAL,
                    technical_depth_score REAL,
                    reflection_score REAL,
                    architecture_reasoning_score REAL,
                    tradeoff_awareness_score REAL,
                    scalability_score REAL,
                    clarity_score REAL,
                    relevance_score REAL,
                    self_awareness_score REAL,
                    communication_score REAL,
                    retry_count_layer1 INTEGER DEFAULT 0,
                    retry_count_layer2 INTEGER DEFAULT 0,
                    retry_count_persist INTEGER DEFAULT 0,
                    error_code TEXT,
                    error_message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(interview_id, turn_id, evaluation_version),
                    UNIQUE(eval_task_key),
                    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interview_evaluations_round_type
                ON interview_evaluations(round_type)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interview_evaluations_position
                ON interview_evaluations(position)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interview_evaluations_rubric_level
                ON interview_evaluations(rubric_level)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interview_evaluations_overall_score
                ON interview_evaluations(overall_score)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interview_evaluations_created_at
                ON interview_evaluations(created_at)
            ''')
            
            conn.commit()
            conn.close()
            print(f"✓ 数据库初始化成功: {self.db_path}")
            
        except Exception as e:
            print(f"✗ 数据库初始化失败: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """
        获取数据库连接的上下文管理器
        
        使用方式：
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(...)
                conn.commit()
        
        Yields:
            sqlite3.Connection: 数据库连接对象
        """
        conn = None
        try:
            # 启用 WAL 模式以提高并发性能
            conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA foreign_keys=ON')
            conn.row_factory = sqlite3.Row  # 使结果可以像字典一样访问
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    def execute_transaction(self, operations):
        """
        执行事务操作（多个SQL语句作为一个原子操作）
        
        Args:
            operations: 操作函数列表，每个函数接收 cursor 作为参数
        
        Returns:
            bool: 事务是否成功
        
        Example:
            def op1(cursor):
                cursor.execute("INSERT INTO interviews ...")
            
            def op2(cursor):
                cursor.execute("INSERT INTO events ...")
            
            db.execute_transaction([op1, op2])
        """
        with self._lock:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    for operation in operations:
                        operation(cursor)
                    conn.commit()
                    return True
            except Exception as e:
                print(f"✗ 事务执行失败: {e}")
                return False
    
    def save_interview(self, interview_data):
        """
        保存面试记录（使用连接上下文管理器）
        
        Args:
            interview_data: 面试数据字典，包含以下字段：
                - interview_id: 面试唯一标识
                - start_time: 开始时间
                - end_time: 结束时间
                - duration: 持续时长（秒）
                - max_probability: 最大作弊概率
                - avg_probability: 平均作弊概率
                - risk_level: 风险等级
                - events_count: 事件总数
                - report_path: 报告文件路径
        
        Returns:
            dict: {'success': bool, 'interview_id': str} 或 {'success': bool, 'error': str}
        """
        with self._lock:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT INTO interviews 
                        (interview_id, start_time, end_time, duration, max_probability, 
                         avg_probability, risk_level, events_count, report_path)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        interview_data['interview_id'],
                        interview_data.get('start_time'),
                        interview_data.get('end_time'),
                        interview_data.get('duration'),
                        interview_data.get('max_probability'),
                        interview_data.get('avg_probability'),
                        interview_data.get('risk_level'),
                        interview_data.get('events_count'),
                        interview_data.get('report_path')
                    ))
                    
                    conn.commit()
                    
                    print(f"✓ 面试记录已保存: {interview_data['interview_id']}")
                    return {
                        'success': True,
                        'interview_id': interview_data['interview_id']
                    }
                    
            except sqlite3.IntegrityError:
                print(f"✗ 面试ID已存在: {interview_data['interview_id']}")
                return {
                    'success': False,
                    'error': 'Interview ID already exists'
                }
            except Exception as e:
                print(f"✗ 保存面试记录失败: {e}")
                return {
                    'success': False,
                    'error': str(e)
                }
    
    def save_events(self, interview_id, events):
        """
        批量保存事件记录（使用事务确保原子性）
        
        Args:
            interview_id: 面试ID
            events: 事件列表，每个事件包含：
                - type: 事件类型
                - timestamp: 时间戳
                - score: 分数（可选）
                - description: 描述（可选）
                - 其他自定义字段
        
        Returns:
            dict: {'success': bool, 'count': int} 或 {'success': bool, 'error': str}
        """
        if not events:
            return {'success': True, 'count': 0}
        
        with self._lock:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # 使用批量插入提高性能
                    data = [
                        (
                            interview_id,
                            event.get('type', 'unknown'),
                            event.get('timestamp', 0),
                            event.get('score', 0),
                            event.get('description', ''),
                            json.dumps(event, ensure_ascii=False)
                        )
                        for event in events
                    ]
                    
                    cursor.executemany('''
                        INSERT INTO events 
                        (interview_id, event_type, timestamp, score, description, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', data)
                    
                    conn.commit()
                    count = len(events)
                    
                    print(f"✓ 已保存 {count} 个事件记录")
                    return {'success': True, 'count': count}
                    
            except Exception as e:
                print(f"✗ 保存事件记录失败: {e}")
                return {'success': False, 'error': str(e)}
    
    def save_statistics(self, interview_id, stats):
        """
        保存统计数据
        
        Args:
            interview_id: 面试ID
            stats: 统计数据字典，包含：
                - total_deviations: 眼神偏离次数
                - total_mouth_open: 张嘴次数
                - total_multi_person: 多人出现次数
                - off_screen_ratio: 离屏比例
                - frames_processed: 处理帧数
        
        Returns:
            dict: {'success': bool} 或 {'success': bool, 'error': str}
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO statistics 
                (interview_id, total_deviations, total_mouth_open, 
                 total_multi_person, off_screen_ratio, frames_processed)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                interview_id,
                stats.get('total_deviations', 0),
                stats.get('total_mouth_open', 0),
                stats.get('total_multi_person', 0),
                stats.get('off_screen_ratio', 0.0),
                stats.get('frames_processed', 0)
            ))
            
            conn.commit()
            conn.close()
            
            print(f"✓ 统计数据已保存")
            return {'success': True}
            
        except Exception as e:
            print(f"✗ 保存统计数据失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_interviews(self, limit=100, offset=0, risk_level=None):
        """
        查询面试记录列表
        
        Args:
            limit: 返回数量限制
            offset: 偏移量（用于分页）
            risk_level: 风险等级筛选（可选）
        
        Returns:
            list: 面试记录列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = 'SELECT * FROM interviews'
            params = []
            
            if risk_level:
                query += ' WHERE risk_level = ?'
                params.append(risk_level)
            
            query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            
            conn.close()
            
            # 转换为字典列表
            interviews = []
            for row in rows:
                interview = dict(zip(columns, row))
                interviews.append(interview)
            
            return interviews
            
        except Exception as e:
            print(f"✗ 查询面试记录失败: {e}")
            return []
    
    def get_interview_by_id(self, interview_id):
        """
        根据ID获取面试详情
        
        Args:
            interview_id: 面试ID
        
        Returns:
            dict: 面试记录，如果不存在返回None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT * FROM interviews WHERE interview_id = ?',
                (interview_id,)
            )
            
            columns = [description[0] for description in cursor.description]
            row = cursor.fetchone()
            
            conn.close()
            
            if row:
                return dict(zip(columns, row))
            return None
            
        except Exception as e:
            print(f"✗ 查询面试详情失败: {e}")
            return None
    
    def get_events(self, interview_id, event_type=None):
        """
        获取面试的事件记录
        
        Args:
            interview_id: 面试ID
            event_type: 事件类型筛选（可选）
        
        Returns:
            list: 事件记录列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if event_type:
                cursor.execute('''
                    SELECT * FROM events 
                    WHERE interview_id = ? AND event_type = ?
                    ORDER BY timestamp
                ''', (interview_id, event_type))
            else:
                cursor.execute('''
                    SELECT * FROM events 
                    WHERE interview_id = ?
                    ORDER BY timestamp
                ''', (interview_id,))
            
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            
            conn.close()
            
            # 转换为字典列表
            events = []
            for row in rows:
                event = dict(zip(columns, row))
                # 解析metadata JSON
                if event.get('metadata'):
                    try:
                        event['metadata'] = json.loads(event['metadata'])
                    except:
                        pass
                events.append(event)
            
            return events
            
        except Exception as e:
            print(f"✗ 查询事件记录失败: {e}")
            return []
    
    def get_statistics_summary(self, start_date=None, end_date=None):
        """
        获取统计摘要数据
        
        Args:
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
        
        Returns:
            dict: 统计摘要
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = '''
                SELECT 
                    COUNT(*) as total_interviews,
                    AVG(max_probability) as avg_max_probability,
                    SUM(events_count) as total_events,
                    AVG(duration) as avg_duration
                FROM interviews
            '''
            params = []
            
            if start_date and end_date:
                query += ' WHERE created_at BETWEEN ? AND ?'
                params = [start_date, end_date]
            
            cursor.execute(query, params)
            row = cursor.fetchone()
            
            conn.close()
            
            return {
                'total_interviews': row[0] or 0,
                'avg_max_probability': round(row[1] or 0, 2),
                'total_events': row[2] or 0,
                'avg_duration': round(row[3] or 0, 1)
            }
            
        except Exception as e:
            print(f"✗ 查询统计摘要失败: {e}")
            return {
                'total_interviews': 0,
                'avg_max_probability': 0,
                'total_events': 0,
                'avg_duration': 0
            }
    
    def delete_interview(self, interview_id):
        """
        删除面试记录（包括关联的事件和统计数据）
        
        Args:
            interview_id: 面试ID
        
        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 删除事件记录
            cursor.execute('DELETE FROM events WHERE interview_id = ?', (interview_id,))
            
            # 删除统计数据
            cursor.execute('DELETE FROM statistics WHERE interview_id = ?', (interview_id,))
            
            # 删除面试记录
            cursor.execute('DELETE FROM interviews WHERE interview_id = ?', (interview_id,))
            
            conn.commit()
            conn.close()
            
            print(f"✓ 面试记录已删除: {interview_id}")
            return {
                'success': True,
                'message': 'Interview deleted successfully'
            }
            
        except Exception as e:
            print(f"✗ 删除面试记录失败: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def get_risk_level_distribution(self):
        """
        获取风险等级分布统计
        
        Returns:
            dict: 各风险等级的数量
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT risk_level, COUNT(*) as count
                FROM interviews
                GROUP BY risk_level
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            distribution = {
                'LOW': 0,
                'MEDIUM': 0,
                'HIGH': 0
            }
            
            for row in rows:
                risk_level, count = row
                if risk_level in distribution:
                    distribution[risk_level] = count
            
            return distribution
            
        except Exception as e:
            print(f"✗ 查询风险等级分布失败: {e}")
            return {'LOW': 0, 'MEDIUM': 0, 'HIGH': 0}
    
    def get_event_type_distribution(self, interview_id=None):
        """
        获取事件类型分布统计
        
        Args:
            interview_id: 面试ID（可选，如果提供则只统计该面试）
        
        Returns:
            dict: 各事件类型的数量
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if interview_id:
                cursor.execute('''
                    SELECT event_type, COUNT(*) as count
                    FROM events
                    WHERE interview_id = ?
                    GROUP BY event_type
                ''', (interview_id,))
            else:
                cursor.execute('''
                    SELECT event_type, COUNT(*) as count
                    FROM events
                    GROUP BY event_type
                ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            distribution = {}
            for row in rows:
                event_type, count = row
                distribution[event_type] = count
            
            return distribution
            
        except Exception as e:
            print(f"✗ 查询事件类型分布失败: {e}")
            return {}
    
    def backup_database(self, backup_path=None):
        """
        备份数据库到指定路径
        
        Args:
            backup_path: 备份文件路径，如果为None则自动生成
        
        Returns:
            dict: {'success': bool, 'backup_path': str} 或 {'success': bool, 'error': str}
        """
        try:
            if backup_path is None:
                backup_dir = os.path.join(os.path.dirname(self.db_path), 'backups')
                os.makedirs(backup_dir, exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = os.path.join(backup_dir, f'interview_system_backup_{timestamp}.db')
            
            # 使用 SQLite 的在线备份功能
            with self.get_connection() as source_conn:
                backup_conn = sqlite3.connect(backup_path)
                source_conn.backup(backup_conn)
                backup_conn.close()
            
            print(f"✓ 数据库备份成功: {backup_path}")
            return {
                'success': True,
                'backup_path': backup_path
            }
            
        except Exception as e:
            print(f"✗ 数据库备份失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def restore_database(self, backup_path):
        """
        从备份恢复数据库
        
        Args:
            backup_path: 备份文件路径
        
        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            if not os.path.exists(backup_path):
                return {
                    'success': False,
                    'error': 'Backup file not found'
                }
            
            # 先备份当前数据库
            current_backup = self.db_path + '.before_restore'
            shutil.copy2(self.db_path, current_backup)
            
            # 恢复备份
            shutil.copy2(backup_path, self.db_path)
            
            print(f"✓ 数据库恢复成功，原数据库已备份至: {current_backup}")
            return {
                'success': True,
                'message': 'Database restored successfully',
                'previous_backup': current_backup
            }
            
        except Exception as e:
            print(f"✗ 数据库恢复失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cleanup_old_data(self, days=30):
        """
        清理指定天数之前的旧数据
        
        Args:
            days: 保留最近多少天的数据，默认30天
        
        Returns:
            dict: {'success': bool, 'deleted_count': int}
        """
        with self._lock:
            try:
                cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
                
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # 查询要删除的面试ID
                    cursor.execute('''
                        SELECT interview_id FROM interviews 
                        WHERE created_at < ?
                    ''', (cutoff_date,))
                    
                    interview_ids = [row[0] for row in cursor.fetchall()]
                    
                    if not interview_ids:
                        return {'success': True, 'deleted_count': 0}
                    
                    # 删除关联数据
                    placeholders = ','.join('?' * len(interview_ids))
                    
                    cursor.execute(f'''
                        DELETE FROM events 
                        WHERE interview_id IN ({placeholders})
                    ''', interview_ids)
                    
                    cursor.execute(f'''
                        DELETE FROM statistics 
                        WHERE interview_id IN ({placeholders})
                    ''', interview_ids)
                    
                    cursor.execute(f'''
                        DELETE FROM interviews 
                        WHERE interview_id IN ({placeholders})
                    ''', interview_ids)
                    
                    conn.commit()
                    count = len(interview_ids)
                    
                    print(f"✓ 已清理 {count} 条 {days} 天前的数据")
                    return {
                        'success': True,
                        'deleted_count': count
                    }
                    
            except Exception as e:
                print(f"✗ 数据清理失败: {e}")
                return {
                    'success': False,
                    'error': str(e)
                }
    
    def vacuum_database(self):
        """
        优化数据库，回收已删除数据占用的空间
        
        Returns:
            dict: {'success': bool}
        """
        try:
            with self.get_connection() as conn:
                conn.execute('VACUUM')
                conn.commit()
            
            print("✓ 数据库优化完成")
            return {'success': True}
            
        except Exception as e:
            print(f"✗ 数据库优化失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_database_size(self):
        """
        获取数据库文件大小
        
        Returns:
            dict: {'size_bytes': int, 'size_mb': float}
        """
        try:
            size_bytes = os.path.getsize(self.db_path)
            size_mb = round(size_bytes / (1024 * 1024), 2)
            
            return {
                'size_bytes': size_bytes,
                'size_mb': size_mb
            }
            
        except Exception as e:
            print(f"✗ 获取数据库大小失败: {e}")
            return {
                'size_bytes': 0,
                'size_mb': 0
            }
    
    def close(self):
        """关闭数据库连接（如果有持久连接）"""
        # 使用上下文管理器，连接会自动关闭，无需显式操作
        pass

    # ==================== 简历相关操作 ====================

    def save_resume(self, resume_data):
        """
        保存简历信息

        Args:
            resume_data: 简历数据字典，包含：
                - user_id: 用户 ID
                - file_name: 文件名
                - file_path: 文件路径
                - file_size: 文件大小（字节）
                - file_hash: 文件哈希（用于去重）
                - parsed_data: 解析后的 JSON 数据

        Returns:
            dict: {'success': bool, 'resume_id': int} 或 {'success': bool, 'error': str}
        """
        with self._lock:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()

                    # 解析数据
                    parsed_data = resume_data.get('parsed_data', {})
                    projects = json.dumps(parsed_data.get('projects', []), ensure_ascii=False)
                    experiences = json.dumps(parsed_data.get('experiences', []), ensure_ascii=False)
                    education = json.dumps(parsed_data.get('education', []), ensure_ascii=False)  # 改为数组，支持多个教育经历
                    skills = json.dumps(parsed_data.get('skills', []), ensure_ascii=False)

                    cursor.execute('''
                        INSERT INTO resumes
                        (user_id, file_name, file_path, file_size, file_hash,
                         parsed_data, projects, experiences, education, skills, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        resume_data.get('user_id', 'default'),
                        resume_data['file_name'],
                        resume_data['file_path'],
                        resume_data.get('file_size'),
                        resume_data.get('file_hash'),
                        json.dumps(parsed_data, ensure_ascii=False),
                        projects,
                        experiences,
                        education,
                        skills,
                        resume_data.get('status', 'pending')
                    ))

                    conn.commit()
                    resume_id = cursor.lastrowid

                    print(f"✓ 简历已保存：{resume_data['file_name']} (ID: {resume_id})")
                    return {
                        'success': True,
                        'resume_id': resume_id
                    }

            except Exception as e:
                print(f"✗ 保存简历失败：{e}")
                return {
                    'success': False,
                    'error': str(e)
                }

    def get_resume(self, resume_id):
        """
        根据 ID 获取简历详情

        Args:
            resume_id: 简历 ID

        Returns:
            dict: 简历信息，如果不存在返回 None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                'SELECT * FROM resumes WHERE id = ?',
                (resume_id,)
            )

            columns = [description[0] for description in cursor.description]
            row = cursor.fetchone()

            conn.close()

            if row:
                resume = dict(zip(columns, row))
                # 解析 JSON 字段
                for field in ['parsed_data', 'projects', 'experiences', 'education', 'skills']:
                    if resume.get(field):
                        try:
                            resume[field] = json.loads(resume[field])
                        except:
                            pass
                return resume
            return None

        except Exception as e:
            print(f"✗ 查询简历详情失败：{e}")
            return None

    def get_resumes(self, user_id=None, limit=100, offset=0):
        """
        查询简历列表

        Args:
            user_id: 用户 ID（可选）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            list: 简历列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = 'SELECT * FROM resumes'
            params = []

            if user_id:
                query += ' WHERE user_id = ?'
                params.append(user_id)

            query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            cursor.execute(query, params)

            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()

            conn.close()

            # 转换为字典列表
            resumes = []
            for row in rows:
                resume = dict(zip(columns, row))
                # 解析 JSON 字段
                for field in ['parsed_data', 'projects', 'experiences', 'education', 'skills']:
                    if resume.get(field):
                        try:
                            resume[field] = json.loads(resume[field])
                        except:
                            pass
                resumes.append(resume)

            return resumes

        except Exception as e:
            print(f"✗ 查询简历列表失败：{e}")
            return []

    def update_resume_status(self, resume_id, status, error_message=None):
        """
        更新简历状态

        Args:
            resume_id: 简历 ID
            status: 新状态（pending, parsing, parsed, error）
            error_message: 错误信息（可选）

        Returns:
            bool: 是否成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE resumes
                SET status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, error_message, resume_id))

            conn.commit()
            conn.close()

            print(f"✓ 简历状态已更新：{resume_id} -> {status}")
            return True

        except Exception as e:
            print(f"✗ 更新简历状态失败：{e}")
            return False

    def delete_resume(self, resume_id):
        """
        删除简历记录

        Args:
            resume_id: 简历 ID

        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 先获取文件路径以便删除文件
            cursor.execute('SELECT file_path FROM resumes WHERE id = ?', (resume_id,))
            row = cursor.fetchone()

            if row:
                file_path = row[0]
                # 删除文件
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"✓ 简历文件已删除：{file_path}")
                except Exception as e:
                    print(f"⚠️  删除文件失败：{e}")

                # 删除记录
                cursor.execute('DELETE FROM resumes WHERE id = ?', (resume_id,))
                conn.commit()
                print(f"✓ 简历记录已删除：{resume_id}")

            conn.close()

            return {
                'success': True,
                'message': 'Resume deleted successfully'
            }

        except Exception as e:
            print(f"✗ 删除简历失败：{e}")
            return {
                'success': False,
                'message': str(e)
            }

    def get_latest_resume(self, user_id=None):
        """
        获取最新的简历

        Args:
            user_id: 用户 ID（可选）

        Returns:
            dict: 最新简历信息，如果不存在返回 None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = 'SELECT * FROM resumes'
            params = []

            if user_id:
                query += ' WHERE user_id = ?'
                params.append(user_id)

            query += ' ORDER BY created_at DESC LIMIT 1'

            cursor.execute(query, params)

            columns = [description[0] for description in cursor.description]
            row = cursor.fetchone()

            conn.close()

            if row:
                resume = dict(zip(columns, row))
                # 解析 JSON 字段
                for field in ['parsed_data', 'projects', 'experiences', 'education', 'skills']:
                    if resume.get(field):
                        try:
                            resume[field] = json.loads(resume[field])
                        except:
                            pass
                return resume
            return None

        except Exception as e:
            print(f"✗ 查询最新简历失败：{e}")
            return None

    # ==================== 面试轮次相关操作 ====================

    def save_interview_round(self, round_data):
        """
        保存面试轮次配置

        Args:
            round_data: 轮次数据字典，包含：
                - round_type: 'technical' | 'project' | 'system_design' | 'hr'
                - position: 职位名称
                - difficulty: 难度
                - questions: JSON 数组
                - description: 描述

        Returns:
            dict: {'success': bool, 'round_id': int}
        """
        with self._lock:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()

                    cursor.execute('''
                        INSERT INTO interview_rounds
                        (round_type, position, difficulty, questions, description)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        round_data['round_type'],
                        round_data['position'],
                        round_data.get('difficulty', 'medium'),
                        json.dumps(round_data.get('questions', []), ensure_ascii=False),
                        round_data.get('description', '')
                    ))

                    conn.commit()
                    round_id = cursor.lastrowid

                    print(f"✓ 面试轮次已保存：{round_data['round_type']} (ID: {round_id})")
                    return {
                        'success': True,
                        'round_id': round_id
                    }

            except Exception as e:
                print(f"✗ 保存面试轮次失败：{e}")
                return {
                    'success': False,
                    'error': str(e)
                }

    def get_interview_round_config(self, round_type: str, position: str = None):
        """
        获取面试轮次配置

        Args:
            round_type: 轮次类型
            position: 职位名称（可选）

        Returns:
            dict: 轮次配置
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if position:
                cursor.execute('''
                    SELECT * FROM interview_rounds
                    WHERE round_type = ? AND position = ?
                    ORDER BY created_at DESC LIMIT 1
                ''', (round_type, position))
            else:
                cursor.execute('''
                    SELECT * FROM interview_rounds
                    WHERE round_type = ?
                    ORDER BY created_at DESC LIMIT 1
                ''', (round_type,))

            columns = [description[0] for description in cursor.description]
            row = cursor.fetchone()
            conn.close()

            if row:
                config = dict(zip(columns, row))
                if config.get('questions'):
                    try:
                        config['questions'] = json.loads(config['questions'])
                    except:
                        pass
                return config
            return None

        except Exception as e:
            print(f"✗ 查询面试轮次配置失败：{e}")
            return None

    def save_interview_dialogue(self, dialogue_data):
        """
        保存面试对话记录

        Args:
            dialogue_data: 对话数据字典，包含：
                - interview_id: 面试 ID
                - round_type: 轮次类型
                - question: 问题
                - answer: 回答
                - llm_feedback: LLM 反馈
                - score: 评分

        Returns:
            dict: {'success': bool, 'dialogue_id': int}
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO interview_dialogues
                (interview_id, round_type, question, answer, llm_feedback, score)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                dialogue_data['interview_id'],
                dialogue_data['round_type'],
                dialogue_data['question'],
                dialogue_data.get('answer', ''),
                dialogue_data.get('llm_feedback', ''),
                dialogue_data.get('score', 0)
            ))

            conn.commit()
            dialogue_id = cursor.lastrowid
            conn.close()

            print(f"✓ 面试对话已保存 (ID: {dialogue_id})")
            return {
                'success': True,
                'dialogue_id': dialogue_id
            }

        except Exception as e:
            print(f"✗ 保存面试对话失败：{e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_interview_dialogues(self, interview_id: str):
        """
        获取面试对话历史

        Args:
            interview_id: 面试 ID

        Returns:
            list: 对话记录列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM interview_dialogues
                WHERE interview_id = ?
                ORDER BY created_at
            ''', (interview_id,))

            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            conn.close()

            return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            print(f"✗ 查询面试对话失败：{e}")
            return []

    def save_or_update_speech_evaluation(self, payload):
        """
        保存或更新整题语音表达评估结果（interview_id + turn_id 幂等）。
        """
        columns = [
            'interview_id',
            'turn_id',
            'answer_session_id',
            'round_type',
            'final_transcript',
            'word_timestamps_json',
            'pause_events_json',
            'filler_events_json',
            'speech_metrics_final_json',
            'realtime_metrics_json',
        ]
        values = [payload.get(col) for col in columns]
        placeholders = ', '.join(['?'] * len(columns))
        update_cols = [col for col in columns if col not in ('interview_id', 'turn_id')]
        update_set = ', '.join([f"{col}=excluded.{col}" for col in update_cols] + ["updated_at=CURRENT_TIMESTAMP"])

        sql = f'''
            INSERT INTO speech_evaluations ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(interview_id, turn_id)
            DO UPDATE SET {update_set}
        '''

        with self._lock:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(sql, values)
                    conn.commit()
                    cursor.execute(
                        '''
                        SELECT id
                        FROM speech_evaluations
                        WHERE interview_id = ? AND turn_id = ?
                        LIMIT 1
                        ''',
                        (payload.get('interview_id', ''), payload.get('turn_id', ''))
                    )
                    row = cursor.fetchone()
                    return {
                        'success': True,
                        'id': int(row['id']) if row and row['id'] is not None else 0,
                    }
            except Exception as e:
                print(f"✗ 保存语音评估失败：{e}")
                return {'success': False, 'error': str(e)}

    def get_speech_evaluations(self, interview_id: str, start_time: str = None, end_time: str = None):
        """
        获取语音表达评估结果，可按 created_at 时间范围筛选。
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if start_time and end_time:
                    cursor.execute(
                        '''
                        SELECT *
                        FROM speech_evaluations
                        WHERE interview_id = ?
                          AND datetime(created_at) >= datetime(?)
                          AND datetime(created_at) <= datetime(?)
                        ORDER BY datetime(created_at) ASC
                        ''',
                        (interview_id, start_time, end_time)
                    )
                else:
                    cursor.execute(
                        '''
                        SELECT *
                        FROM speech_evaluations
                        WHERE interview_id = ?
                        ORDER BY datetime(created_at) ASC
                        ''',
                        (interview_id,)
                    )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"✗ 查询语音评估失败：{e}")
            return []

    def save_or_update_evaluation(self, evaluation_data):
        """
        保存或更新单题评估结果（基于 interview_id+turn_id+evaluation_version 幂等）。

        Args:
            evaluation_data: 评估数据字典

        Returns:
            dict: {'success': bool, 'id': int}
        """
        columns = [
            'interview_id', 'turn_id', 'question_id', 'user_id', 'round_type', 'position',
            'question', 'answer', 'evaluation_version', 'rubric_version', 'prompt_version',
            'llm_model', 'eval_task_key', 'status', 'layer1_json', 'layer2_json',
            'rubric_level', 'overall_score', 'confidence',
            'technical_accuracy_score', 'knowledge_depth_score', 'completeness_score',
            'logic_score', 'job_match_score',
            'authenticity_score', 'ownership_score', 'technical_depth_score', 'reflection_score',
            'architecture_reasoning_score', 'tradeoff_awareness_score', 'scalability_score',
            'clarity_score', 'relevance_score', 'self_awareness_score', 'communication_score',
            'retry_count_layer1', 'retry_count_layer2', 'retry_count_persist',
            'error_code', 'error_message'
        ]

        values = [evaluation_data.get(col) for col in columns]

        placeholders = ', '.join(['?'] * len(columns))
        update_columns = [col for col in columns if col not in ('interview_id', 'turn_id', 'evaluation_version')]
        update_set = ', '.join([f"{col}=excluded.{col}" for col in update_columns] + ["updated_at=CURRENT_TIMESTAMP"])

        sql = f'''
            INSERT INTO interview_evaluations ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(interview_id, turn_id, evaluation_version)
            DO UPDATE SET {update_set}
        '''

        with self._lock:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(sql, values)
                    conn.commit()

                    cursor.execute(
                        '''
                        SELECT id
                        FROM interview_evaluations
                        WHERE interview_id = ? AND turn_id = ? AND evaluation_version = ?
                        LIMIT 1
                        ''',
                        (
                            evaluation_data.get('interview_id', ''),
                            evaluation_data.get('turn_id', ''),
                            evaluation_data.get('evaluation_version', 'v1'),
                        )
                    )
                    row = cursor.fetchone()
                    return {
                        'success': True,
                        'id': int(row['id']) if row and row['id'] is not None else 0
                    }
            except Exception as e:
                print(f"✗ 保存评估记录失败：{e}")
                return {
                    'success': False,
                    'error': str(e)
                }

    def get_interview_evaluations(self, interview_id: str, evaluation_version: str = None):
        """
        获取指定面试的评估记录。
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if evaluation_version:
                    cursor.execute(
                        '''
                        SELECT *
                        FROM interview_evaluations
                        WHERE interview_id = ? AND evaluation_version = ?
                        ORDER BY created_at ASC
                        ''',
                        (interview_id, evaluation_version)
                    )
                else:
                    cursor.execute(
                        '''
                        SELECT *
                        FROM interview_evaluations
                        WHERE interview_id = ?
                        ORDER BY created_at ASC
                        ''',
                        (interview_id,)
                    )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"✗ 查询评估记录失败：{e}")
            return []

    def get_evaluation_record(
        self,
        interview_id: str,
        turn_id: str,
        evaluation_version: str = "v1"
    ):
        """
        按唯一键获取单题评估记录。
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT *
                    FROM interview_evaluations
                    WHERE interview_id = ? AND turn_id = ? AND evaluation_version = ?
                    LIMIT 1
                    ''',
                    (interview_id, turn_id, evaluation_version)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"✗ 查询单题评估记录失败：{e}")
            return None


if __name__ == '__main__':
    # 测试代码
    print("测试数据库管理器...")
    
    # 创建测试数据库
    db = DatabaseManager('test_interview.db')
    
    # 测试保存面试记录
    test_interview = {
        'interview_id': 'test_001',
        'start_time': datetime.now().isoformat(),
        'end_time': datetime.now().isoformat(),
        'duration': 300,
        'max_probability': 65.5,
        'avg_probability': 32.8,
        'risk_level': 'MEDIUM',
        'events_count': 5,
        'report_path': 'reports/test_001.pdf'
    }
    
    result = db.save_interview(test_interview)
    print(f"保存面试: {result}")
    
    # 测试保存事件
    test_events = [
        {
            'type': 'gaze_deviation',
            'timestamp': 1234567890.123,
            'score': 30,
            'description': '眼神向左偏离'
        },
        {
            'type': 'mouth_open',
            'timestamp': 1234567895.456,
            'score': 20,
            'description': '嘴部张开'
        }
    ]
    
    result = db.save_events('test_001', test_events)
    print(f"保存事件: {result}")
    
    # 测试查询
    interviews = db.get_interviews(limit=10)
    print(f"查询面试记录: {len(interviews)} 条")
    
    events = db.get_events('test_001')
    print(f"查询事件记录: {len(events)} 条")
    
    # 测试统计
    summary = db.get_statistics_summary()
    print(f"统计摘要: {summary}")
    
    print("✓ 数据库管理器测试完成")
