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
import re
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

    @staticmethod
    def _interview_evaluations_compat_columns():
        """返回 interview_evaluations 兼容所需列定义。"""
        return [
            ('text_layer_json', 'TEXT'),
            ('speech_layer_json', 'TEXT'),
            ('video_layer_json', 'TEXT'),
            ('fusion_json', 'TEXT'),
            ('scoring_snapshot_json', 'TEXT'),
            ('confidence_score', 'REAL'),
            ('gaze_focus_score', 'REAL'),
            ('posture_compliance_score', 'REAL'),
            ('physiology_stability_score', 'REAL'),
            ('expression_naturalness_score', 'REAL'),
            ('engagement_level_score', 'REAL'),
            ('retry_count_layer1', 'INTEGER DEFAULT 0'),
            ('retry_count_layer2', 'INTEGER DEFAULT 0'),
            ('retry_count_persist', 'INTEGER DEFAULT 0'),
            ('error_code', 'TEXT'),
            ('error_message', 'TEXT'),
        ]

    def _ensure_interview_evaluations_schema(self, conn) -> None:
        """兼容旧库：确保 interview_evaluations 具备当前写入所需字段。"""
        for col_name, col_def in self._interview_evaluations_compat_columns():
            self._ensure_column_exists(
                conn=conn,
                table_name='interview_evaluations',
                column_name=col_name,
                column_def=col_def,
            )
    
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

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS resume_optimizations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    optimization_id TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    resume_id INTEGER,
                    target_role TEXT,
                    strategy TEXT DEFAULT 'keywords',
                    job_description TEXT,
                    match_before REAL DEFAULT 0,
                    match_after REAL DEFAULT 0,
                    result_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (resume_id) REFERENCES resumes(id)
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_resume_optimizations_user_id
                ON resume_optimizations(user_id)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_resume_optimizations_created_at
                ON resume_optimizations(created_at DESC)
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    is_demo INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_users_email
                ON users(email)
            ''')

            self._ensure_column_exists(conn, 'users', 'membership_status', "TEXT DEFAULT 'inactive'")
            self._ensure_column_exists(conn, 'users', 'membership_mode', 'TEXT')
            self._ensure_column_exists(conn, 'users', 'membership_plan_id', 'TEXT')
            self._ensure_column_exists(conn, 'users', 'membership_team_size', 'INTEGER DEFAULT 1')
            self._ensure_column_exists(conn, 'users', 'membership_cycle_quota', 'INTEGER DEFAULT 0')
            self._ensure_column_exists(conn, 'users', 'membership_cycle_used', 'INTEGER DEFAULT 0')
            self._ensure_column_exists(conn, 'users', 'membership_auto_renew', 'INTEGER DEFAULT 0')
            self._ensure_column_exists(conn, 'users', 'membership_started_at', 'DATETIME')
            self._ensure_column_exists(conn, 'users', 'membership_expires_at', 'DATETIME')
            self._ensure_column_exists(conn, 'users', 'membership_updated_at', 'DATETIME')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS membership_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL UNIQUE,
                    user_email TEXT NOT NULL,
                    membership_mode TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    team_size INTEGER NOT NULL DEFAULT 1,
                    unit_price REAL NOT NULL DEFAULT 0,
                    total_price REAL NOT NULL DEFAULT 0,
                    quota_total INTEGER DEFAULT 0,
                    quota_used INTEGER DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_membership_orders_user_email
                ON membership_orders(user_email)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_membership_orders_status
                ON membership_orders(status)
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_notification_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL UNIQUE,
                    in_app_enabled INTEGER DEFAULT 1,
                    inactivity_24h_enabled INTEGER DEFAULT 1,
                    streak_enabled INTEGER DEFAULT 1,
                    weekly_plan_due_enabled INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_notification_settings_user_id
                ON user_notification_settings(user_id)
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS assistant_conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    last_message_preview TEXT,
                    archived INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_assistant_conversations_user_id
                ON assistant_conversations(user_id)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_assistant_conversations_updated_at
                ON assistant_conversations(updated_at DESC)
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS assistant_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT UNIQUE NOT NULL,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    message_type TEXT DEFAULT 'text',
                    citations_json TEXT,
                    answer_mode TEXT,
                    retrieval_meta_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES assistant_conversations(conversation_id)
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_assistant_messages_conversation_id
                ON assistant_messages(conversation_id)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_assistant_messages_created_at
                ON assistant_messages(created_at ASC)
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
                    turn_id TEXT,
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

            # 兼容旧库：若 interview_dialogues 缺少 turn_id 列则先补齐，再建索引
            self._ensure_column_exists(
                conn=conn,
                table_name='interview_dialogues',
                column_name='turn_id',
                column_def='TEXT'
            )
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interview_dialogues_turn_id
                ON interview_dialogues(turn_id)
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
                    text_layer_json TEXT,
                    speech_layer_json TEXT,
                    video_layer_json TEXT,
                    fusion_json TEXT,
                    scoring_snapshot_json TEXT,
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
                    confidence_score REAL,
                    gaze_focus_score REAL,
                    posture_compliance_score REAL,
                    physiology_stability_score REAL,
                    expression_naturalness_score REAL,
                    engagement_level_score REAL,
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

            # 评分链路事件日志
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS evaluation_traces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT NOT NULL,
                    interview_id TEXT NOT NULL,
                    turn_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    status TEXT,
                    duration_ms REAL,
                    payload_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_evaluation_traces_interview_turn
                ON evaluation_traces(interview_id, turn_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_evaluation_traces_trace_id
                ON evaluation_traces(trace_id)
            ''')

            # 复盘视频资产表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interview_assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interview_id TEXT NOT NULL UNIQUE,
                    upload_id TEXT,
                    storage_key TEXT,
                    video_url TEXT,
                    local_path TEXT,
                    duration_ms REAL DEFAULT 0,
                    codec TEXT,
                    status TEXT DEFAULT 'uploaded',
                    metadata_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interview_assets_status
                ON interview_assets(status)
            ''')

            # 题目级时间轴锚点
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interview_turn_timeline (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interview_id TEXT NOT NULL,
                    turn_id TEXT NOT NULL,
                    question_start_ms REAL,
                    question_end_ms REAL,
                    answer_start_ms REAL,
                    answer_end_ms REAL,
                    latency_ms REAL,
                    source TEXT DEFAULT 'runtime',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(interview_id, turn_id),
                    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interview_turn_timeline_interview_id
                ON interview_turn_timeline(interview_id)
            ''')

            # A/E 标签统一存储
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interview_timeline_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interview_id TEXT NOT NULL,
                    turn_id TEXT,
                    tag_type TEXT NOT NULL,
                    start_ms REAL NOT NULL,
                    end_ms REAL NOT NULL,
                    reason TEXT,
                    confidence REAL DEFAULT 0,
                    evidence_json TEXT,
                    source TEXT DEFAULT 'review_service',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interview_timeline_tags_interview_id
                ON interview_timeline_tags(interview_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interview_timeline_tags_start_ms
                ON interview_timeline_tags(start_ms)
            ''')

            # B 深度技术诊断
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interview_deep_audits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interview_id TEXT NOT NULL UNIQUE,
                    fact_checks_json TEXT,
                    dimension_gaps_json TEXT,
                    round_diagnosis_json TEXT,
                    version TEXT DEFAULT 'v1',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
                )
            ''')

            # C 影子回答
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interview_shadow_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interview_id TEXT NOT NULL,
                    turn_id TEXT NOT NULL,
                    question TEXT,
                    original_answer TEXT,
                    shadow_answer TEXT,
                    why_better TEXT,
                    resume_alignment_json TEXT,
                    version TEXT DEFAULT 'v1',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(interview_id, turn_id, version),
                    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interview_shadow_answers_interview_id
                ON interview_shadow_answers(interview_id)
            ''')

            # D 可视化评估矩阵
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interview_visual_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interview_id TEXT NOT NULL UNIQUE,
                    latency_matrix_json TEXT,
                    keyword_coverage_json TEXT,
                    speech_tone_json TEXT,
                    radar_json TEXT,
                    heatmap_json TEXT,
                    version TEXT DEFAULT 'v1',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
                )
            ''')

            # 训练闭环：周计划
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS training_week_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id TEXT NOT NULL UNIQUE,
                    user_id TEXT NOT NULL,
                    week_start_date TEXT NOT NULL,
                    week_end_date TEXT NOT NULL,
                    target_position TEXT,
                    status TEXT DEFAULT 'active',
                    source_summary_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, week_start_date)
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_training_week_plans_user_week
                ON training_week_plans(user_id, week_start_date)
            ''')

            # 训练闭环：任务
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS training_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL UNIQUE,
                    plan_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    round_type TEXT NOT NULL,
                    position TEXT,
                    difficulty TEXT,
                    focus_key TEXT,
                    focus_label TEXT,
                    goal_score REAL DEFAULT 75,
                    status TEXT DEFAULT 'planned',
                    priority INTEGER DEFAULT 0,
                    from_task_id TEXT,
                    last_interview_id TEXT,
                    last_score REAL,
                    training_started_at DATETIME,
                    validation_started_at DATETIME,
                    due_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (plan_id) REFERENCES training_week_plans(plan_id)
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_training_tasks_plan_id
                ON training_tasks(plan_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_training_tasks_user_status
                ON training_tasks(user_id, status)
            ''')

            # 训练闭环：尝试记录
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS training_task_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attempt_id TEXT NOT NULL UNIQUE,
                    task_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    attempt_type TEXT NOT NULL,
                    interview_id TEXT,
                    score REAL,
                    passed INTEGER,
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES training_tasks(task_id)
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_training_task_attempts_task_id
                ON training_task_attempts(task_id)
            ''')

            # 训练闭环：验收结论
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS training_task_validations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    validation_id TEXT NOT NULL UNIQUE,
                    task_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    validation_interview_id TEXT,
                    score REAL,
                    passed INTEGER,
                    decision TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES training_tasks(task_id)
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_training_task_validations_task_id
                ON training_task_validations(task_id)
            ''')

            # 兼容逻辑保留（幂等）
            self._ensure_column_exists(conn, 'statistics', 'avg_heart_rate', 'REAL')
            self._ensure_column_exists(conn, 'statistics', 'rppg_reliable_ratio', 'REAL')
            self._ensure_column_exists(conn, 'statistics', 'heart_rate_samples', 'INTEGER DEFAULT 0')
            self._ensure_column_exists(
                conn=conn,
                table_name='interview_dialogues',
                column_name='turn_id',
                column_def='TEXT'
            )
            self._ensure_interview_evaluations_schema(conn)
            
            conn.commit()
            conn.close()
            print(f"✓ 数据库初始化成功: {self.db_path}")
            
        except Exception as e:
            print(f"✗ 数据库初始化失败: {e}")
            raise

    @staticmethod
    def _ensure_column_exists(conn, table_name: str, column_name: str, column_def: str) -> None:
        """兼容旧库表结构：缺列时自动 ALTER TABLE 新增。"""
        try:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [str(row[1]).strip().lower() for row in cursor.fetchall()]
            if str(column_name).strip().lower() not in columns:
                cursor.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"
                )
        except Exception:
            # 兼容失败不影响主流程，后续业务可继续运行
            pass
    
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
                        ON CONFLICT(interview_id) DO UPDATE SET
                            start_time = COALESCE(excluded.start_time, interviews.start_time),
                            end_time = COALESCE(excluded.end_time, interviews.end_time),
                            duration = COALESCE(excluded.duration, interviews.duration),
                            max_probability = COALESCE(excluded.max_probability, interviews.max_probability),
                            avg_probability = COALESCE(excluded.avg_probability, interviews.avg_probability),
                            risk_level = COALESCE(excluded.risk_level, interviews.risk_level),
                            events_count = COALESCE(excluded.events_count, interviews.events_count),
                            report_path = COALESCE(excluded.report_path, interviews.report_path)
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
            with self._lock:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO statistics
                        (interview_id, total_deviations, total_mouth_open,
                         total_multi_person, off_screen_ratio, frames_processed,
                         avg_heart_rate, rppg_reliable_ratio, heart_rate_samples)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(interview_id) DO UPDATE SET
                            total_deviations = excluded.total_deviations,
                            total_mouth_open = excluded.total_mouth_open,
                            total_multi_person = excluded.total_multi_person,
                            off_screen_ratio = excluded.off_screen_ratio,
                            frames_processed = excluded.frames_processed,
                            avg_heart_rate = excluded.avg_heart_rate,
                            rppg_reliable_ratio = excluded.rppg_reliable_ratio,
                            heart_rate_samples = excluded.heart_rate_samples
                    ''', (
                        interview_id,
                        stats.get('total_deviations', 0),
                        stats.get('total_mouth_open', 0),
                        stats.get('total_multi_person', 0),
                        stats.get('off_screen_ratio', 0.0),
                        stats.get('frames_processed', 0),
                        stats.get('avg_heart_rate'),
                        stats.get('rppg_reliable_ratio'),
                        stats.get('heart_rate_samples', 0)
                    ))
                    conn.commit()

            print(f"✓ 统计数据已保存")
            return {'success': True}

        except Exception as e:
            print(f"✗ 保存统计数据失败: {e}")
            return {'success': False, 'error': str(e)}

    def get_statistics_by_interview(self, interview_id: str):
        """读取单场统计数据。"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT * FROM statistics
                    WHERE interview_id = ?
                    LIMIT 1
                    ''',
                    (interview_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"✗ 查询统计数据失败：{e}")
            return None
    
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

    def save_resume_optimization(self, optimization_data):
        """保存简历优化结果。"""
        with self._lock:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO resume_optimizations
                        (optimization_id, user_id, resume_id, target_role, strategy, job_description,
                         match_before, match_after, result_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        optimization_data['optimization_id'],
                        optimization_data.get('user_id', 'default'),
                        optimization_data.get('resume_id'),
                        optimization_data.get('target_role'),
                        optimization_data.get('strategy', 'keywords'),
                        optimization_data.get('job_description', ''),
                        optimization_data.get('match_before', 0),
                        optimization_data.get('match_after', 0),
                        json.dumps(optimization_data.get('result', {}), ensure_ascii=False),
                    ))
                    conn.commit()
                    return {
                        'success': True,
                        'optimization_db_id': cursor.lastrowid,
                        'optimization_id': optimization_data['optimization_id'],
                    }
            except Exception as e:
                print(f"✗ 保存简历优化结果失败：{e}")
                return {
                    'success': False,
                    'error': str(e),
                }

    def get_resume_optimizations(self, user_id=None, limit=20, offset=0):
        """获取简历优化历史列表。"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = '''
                SELECT ro.*, r.file_name AS resume_file_name
                FROM resume_optimizations ro
                LEFT JOIN resumes r ON r.id = ro.resume_id
            '''
            params = []
            if user_id:
                query += ' WHERE ro.user_id = ?'
                params.append(user_id)
            query += ' ORDER BY ro.created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            history = []
            for row in rows:
                item = dict(row)
                if item.get('result_json'):
                    try:
                        item['result'] = json.loads(item['result_json'])
                    except Exception:
                        item['result'] = None
                history.append(item)
            return history
        except Exception as e:
            print(f"✗ 查询简历优化历史失败：{e}")
            return []

    def get_resume_optimization(self, optimization_id, user_id=None):
        """获取单条简历优化详情。"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = '''
                SELECT ro.*, r.file_name AS resume_file_name
                FROM resume_optimizations ro
                LEFT JOIN resumes r ON r.id = ro.resume_id
                WHERE ro.optimization_id = ?
            '''
            params = [optimization_id]
            if user_id:
                query += ' AND ro.user_id = ?'
                params.append(user_id)
            query += ' LIMIT 1'
            cursor.execute(query, params)
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            item = dict(row)
            if item.get('result_json'):
                try:
                    item['result'] = json.loads(item['result_json'])
                except Exception:
                    item['result'] = None
            return item
        except Exception as e:
            print(f"✗ 查询简历优化详情失败：{e}")
            return None

    # ==================== 面试轮次相关操作 ====================

    @staticmethod
    def _normalize_user_email(email):
        return str(email or '').strip().lower()

    @staticmethod
    def _serialize_user_row(row):
        if not row:
            return None
        item = dict(row)
        return {
            'id': item.get('id'),
            'email': str(item.get('email') or '').strip().lower(),
            'display_name': str(item.get('display_name') or '').strip(),
            'is_demo': bool(item.get('is_demo')),
            'membership_status': str(item.get('membership_status') or 'inactive').strip() or 'inactive',
            'membership_mode': str(item.get('membership_mode') or '').strip() or None,
            'membership_plan_id': str(item.get('membership_plan_id') or '').strip() or None,
            'membership_team_size': max(1, int(item.get('membership_team_size') or 1)),
            'membership_cycle_quota': int(item.get('membership_cycle_quota') or 0),
            'membership_cycle_used': int(item.get('membership_cycle_used') or 0),
            'membership_auto_renew': bool(item.get('membership_auto_renew', 0)),
            'membership_started_at': item.get('membership_started_at'),
            'membership_expires_at': item.get('membership_expires_at'),
            'membership_updated_at': item.get('membership_updated_at'),
            'created_at': item.get('created_at'),
            'updated_at': item.get('updated_at'),
        }

    def get_user_by_email(self, email):
        normalized_email = self._normalize_user_email(email)
        if not normalized_email:
            return None
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT
                        id,
                        email,
                        password_hash,
                        display_name,
                        is_demo,
                        membership_status,
                        membership_mode,
                        membership_plan_id,
                        membership_team_size,
                        membership_cycle_quota,
                        membership_cycle_used,
                        membership_auto_renew,
                        membership_started_at,
                        membership_expires_at,
                        membership_updated_at,
                        created_at,
                        updated_at
                    FROM users
                    WHERE email = ?
                    LIMIT 1
                    ''',
                    (normalized_email,)
                )
                row = cursor.fetchone()
                if not row:
                    return None
                item = dict(row)
                item['email'] = normalized_email
                item['display_name'] = str(item.get('display_name') or '').strip()
                item['is_demo'] = bool(item.get('is_demo'))
                return item
        except Exception as e:
            print(f"get_user_by_email failed: {e}")
            return None

    def update_password(self, email, new_password_hash):
        normalized_email = self._normalize_user_email(email)
        normalized_hash = str(new_password_hash or '').strip()
        if not normalized_email or not normalized_hash:
            return {'success': False, 'error': 'invalid payload'}
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE email = ?',
                    (normalized_hash, normalized_email)
                )
                conn.commit()
                if cursor.rowcount == 0:
                    return {'success': False, 'error': 'user not found'}
                return {'success': True}
        except Exception as e:
            print(f"update_password failed: {e}")
            return {'success': False, 'error': str(e)}

    def create_user(self, email, password_hash, display_name, is_demo=False):
        normalized_email = self._normalize_user_email(email)
        normalized_hash = str(password_hash or '').strip()
        normalized_name = str(display_name or '').strip()
        if not normalized_email or not normalized_hash or not normalized_name:
            return {'success': False, 'error': 'invalid user payload'}

        with self._lock:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        '''
                        INSERT INTO users (email, password_hash, display_name, is_demo)
                        VALUES (?, ?, ?, ?)
                        ''',
                        (normalized_email, normalized_hash, normalized_name, 1 if is_demo else 0)
                    )
                    conn.commit()
                    cursor.execute(
                        '''
                        SELECT
                            id,
                            email,
                            display_name,
                            is_demo,
                            membership_status,
                            membership_mode,
                            membership_plan_id,
                            membership_team_size,
                            membership_cycle_quota,
                            membership_cycle_used,
                            membership_auto_renew,
                            membership_started_at,
                            membership_expires_at,
                            membership_updated_at,
                            created_at,
                            updated_at
                        FROM users
                        WHERE email = ?
                        LIMIT 1
                        ''',
                        (normalized_email,)
                    )
                    created = cursor.fetchone()
                    return {'success': True, 'user': self._serialize_user_row(created)}
            except sqlite3.IntegrityError:
                return {'success': False, 'error': 'email already exists'}
            except Exception as e:
                print(f"create_user failed: {e}")
                return {'success': False, 'error': str(e)}

    def ensure_user(self, email, password_hash, display_name, is_demo=False):
        normalized_email = self._normalize_user_email(email)
        normalized_hash = str(password_hash or '').strip()
        normalized_name = str(display_name or '').strip()
        if not normalized_email or not normalized_hash or not normalized_name:
            return {'success': False, 'error': 'invalid user payload'}

        with self._lock:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        '''
                        SELECT
                            id,
                            email,
                            display_name,
                            is_demo,
                            membership_status,
                            membership_mode,
                            membership_plan_id,
                            membership_team_size,
                            membership_cycle_quota,
                            membership_cycle_used,
                            membership_auto_renew,
                            membership_started_at,
                            membership_expires_at,
                            membership_updated_at,
                            created_at,
                            updated_at
                        FROM users
                        WHERE email = ?
                        LIMIT 1
                        ''',
                        (normalized_email,)
                    )
                    existed = cursor.fetchone()
                    if existed:
                        return {
                            'success': True,
                            'created': False,
                            'user': self._serialize_user_row(existed),
                        }

                    cursor.execute(
                        '''
                        INSERT INTO users (email, password_hash, display_name, is_demo)
                        VALUES (?, ?, ?, ?)
                        ''',
                        (normalized_email, normalized_hash, normalized_name, 1 if is_demo else 0)
                    )
                    conn.commit()
                    cursor.execute(
                        '''
                        SELECT
                            id,
                            email,
                            display_name,
                            is_demo,
                            membership_status,
                            membership_mode,
                            membership_plan_id,
                            membership_team_size,
                            membership_cycle_quota,
                            membership_cycle_used,
                            membership_auto_renew,
                            membership_started_at,
                            membership_expires_at,
                            membership_updated_at,
                            created_at,
                            updated_at
                        FROM users
                        WHERE email = ?
                        LIMIT 1
                        ''',
                        (normalized_email,)
                    )
                    created = cursor.fetchone()
                    return {
                        'success': True,
                        'created': True,
                        'user': self._serialize_user_row(created),
                    }
            except Exception as e:
                print(f"ensure_user failed: {e}")
                return {'success': False, 'error': str(e)}

    @staticmethod
    def _serialize_membership_order_row(row):
        if not row:
            return None
        item = dict(row)
        return {
            'order_id': str(item.get('order_id') or '').strip(),
            'user_email': str(item.get('user_email') or '').strip().lower(),
            'membership_mode': str(item.get('membership_mode') or '').strip(),
            'plan_id': str(item.get('plan_id') or '').strip(),
            'team_size': max(1, int(item.get('team_size') or 1)),
            'unit_price': float(item.get('unit_price') or 0),
            'total_price': float(item.get('total_price') or 0),
            'quota_total': int(item.get('quota_total') or 0),
            'quota_used': int(item.get('quota_used') or 0),
            'status': str(item.get('status') or 'pending').strip() or 'pending',
            'created_at': item.get('created_at'),
            'updated_at': item.get('updated_at'),
        }

    def create_membership_order(self, order_data):
        columns = [
            'order_id',
            'user_email',
            'membership_mode',
            'plan_id',
            'team_size',
            'unit_price',
            'total_price',
            'quota_total',
            'quota_used',
            'status',
        ]
        values = [order_data.get(column) for column in columns]
        placeholders = ', '.join(['?'] * len(columns))
        sql = f'''
            INSERT INTO membership_orders ({', '.join(columns)})
            VALUES ({placeholders})
        '''

        try:
            with self._lock:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(sql, values)
                    conn.commit()
                    cursor.execute(
                        '''
                        SELECT *
                        FROM membership_orders
                        WHERE order_id = ?
                        LIMIT 1
                        ''',
                        (str(order_data.get('order_id') or '').strip(),)
                    )
                    row = cursor.fetchone()
                    return {'success': True, 'order': self._serialize_membership_order_row(row)}
        except Exception as e:
            print(f"create_membership_order failed: {e}")
            return {'success': False, 'error': str(e), 'order': None}

    def get_membership_order(self, order_id, user_email=None):
        normalized_order_id = str(order_id or '').strip()
        normalized_email = self._normalize_user_email(user_email) if user_email else ''
        if not normalized_order_id:
            return None
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if normalized_email:
                    cursor.execute(
                        '''
                        SELECT *
                        FROM membership_orders
                        WHERE order_id = ? AND user_email = ?
                        LIMIT 1
                        ''',
                        (normalized_order_id, normalized_email)
                    )
                else:
                    cursor.execute(
                        '''
                        SELECT *
                        FROM membership_orders
                        WHERE order_id = ?
                        LIMIT 1
                        ''',
                        (normalized_order_id,)
                    )
                row = cursor.fetchone()
                return self._serialize_membership_order_row(row)
        except Exception as e:
            print(f"get_membership_order failed: {e}")
            return None

    def list_membership_orders(self, user_email, limit=10):
        normalized_email = self._normalize_user_email(user_email)
        if not normalized_email:
            return []
        safe_limit = max(1, min(int(limit or 10), 50))
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT *
                    FROM membership_orders
                    WHERE user_email = ?
                    ORDER BY datetime(created_at) DESC, id DESC
                    LIMIT ?
                    ''',
                    (normalized_email, safe_limit)
                )
                return [self._serialize_membership_order_row(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"list_membership_orders failed: {e}")
            return []

    def update_membership_order_status(self, order_id, status, quota_used=None):
        normalized_order_id = str(order_id or '').strip()
        normalized_status = str(status or '').strip() or 'pending'
        if not normalized_order_id:
            return {'success': False, 'error': 'invalid order_id'}
        updates = ['status = ?', 'updated_at = CURRENT_TIMESTAMP']
        params = [normalized_status]
        if quota_used is not None:
            updates.append('quota_used = ?')
            params.append(int(quota_used or 0))
        params.append(normalized_order_id)
        sql = f'''
            UPDATE membership_orders
            SET {', '.join(updates)}
            WHERE order_id = ?
        '''
        try:
            with self._lock:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(sql, params)
                    conn.commit()
                    if int(cursor.rowcount or 0) <= 0:
                        return {'success': False, 'error': 'order not found'}
                    return {'success': True}
        except Exception as e:
            print(f"update_membership_order_status failed: {e}")
            return {'success': False, 'error': str(e)}

    def update_user_membership(self, email, membership_data):
        normalized_email = self._normalize_user_email(email)
        if not normalized_email:
            return {'success': False, 'error': 'invalid email'}

        try:
            with self._lock:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        '''
                        UPDATE users
                        SET
                            membership_status = ?,
                            membership_mode = ?,
                            membership_plan_id = ?,
                            membership_team_size = ?,
                            membership_cycle_quota = ?,
                            membership_cycle_used = ?,
                            membership_auto_renew = ?,
                            membership_started_at = ?,
                            membership_expires_at = ?,
                            membership_updated_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE email = ?
                        ''',
                        (
                            str(membership_data.get('membership_status') or 'inactive').strip() or 'inactive',
                            str(membership_data.get('membership_mode') or '').strip() or None,
                            str(membership_data.get('membership_plan_id') or '').strip() or None,
                            max(1, int(membership_data.get('membership_team_size') or 1)),
                            int(membership_data.get('membership_cycle_quota') or 0),
                            int(membership_data.get('membership_cycle_used') or 0),
                            1 if membership_data.get('membership_auto_renew') else 0,
                            membership_data.get('membership_started_at'),
                            membership_data.get('membership_expires_at'),
                            normalized_email,
                        )
                    )
                    conn.commit()
                    if int(cursor.rowcount or 0) <= 0:
                        return {'success': False, 'error': 'user not found'}
                    user = self.get_user_by_email(normalized_email)
                    return {'success': True, 'user': self._serialize_user_row(user)}
        except Exception as e:
            print(f"update_user_membership failed: {e}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    def _serialize_notification_settings_row(row):
        if not row:
            return None
        item = dict(row)
        return {
            'user_id': str(item.get('user_id') or '').strip() or 'default',
            'in_app_enabled': bool(item.get('in_app_enabled', 1)),
            'inactivity_24h_enabled': bool(item.get('inactivity_24h_enabled', 1)),
            'streak_enabled': bool(item.get('streak_enabled', 1)),
            'weekly_plan_due_enabled': bool(item.get('weekly_plan_due_enabled', 1)),
            'created_at': item.get('created_at'),
            'updated_at': item.get('updated_at'),
        }

    def get_notification_settings(self, user_id='default'):
        normalized_user_id = str(user_id or 'default').strip().lower() or 'default'
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT *
                    FROM user_notification_settings
                    WHERE user_id = ?
                    LIMIT 1
                    ''',
                    (normalized_user_id,)
                )
                row = cursor.fetchone()
                if row:
                    return self._serialize_notification_settings_row(row)
                return {
                    'user_id': normalized_user_id,
                    'in_app_enabled': True,
                    'inactivity_24h_enabled': True,
                    'streak_enabled': True,
                    'weekly_plan_due_enabled': True,
                    'created_at': None,
                    'updated_at': None,
                }
        except Exception as e:
            print(f"get_notification_settings failed: {e}")
            return {
                'user_id': normalized_user_id,
                'in_app_enabled': True,
                'inactivity_24h_enabled': True,
                'streak_enabled': True,
                'weekly_plan_due_enabled': True,
                'created_at': None,
                'updated_at': None,
            }

    def upsert_notification_settings(self, settings_data):
        normalized_user_id = str((settings_data or {}).get('user_id') or 'default').strip().lower() or 'default'
        normalized_payload = {
            'user_id': normalized_user_id,
            'in_app_enabled': 1 if bool((settings_data or {}).get('in_app_enabled', True)) else 0,
            'inactivity_24h_enabled': 1 if bool((settings_data or {}).get('inactivity_24h_enabled', True)) else 0,
            'streak_enabled': 1 if bool((settings_data or {}).get('streak_enabled', True)) else 0,
            'weekly_plan_due_enabled': 1 if bool((settings_data or {}).get('weekly_plan_due_enabled', True)) else 0,
        }

        try:
            with self._lock:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        '''
                        INSERT INTO user_notification_settings (
                            user_id,
                            in_app_enabled,
                            inactivity_24h_enabled,
                            streak_enabled,
                            weekly_plan_due_enabled
                        ) VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(user_id)
                        DO UPDATE SET
                            in_app_enabled = excluded.in_app_enabled,
                            inactivity_24h_enabled = excluded.inactivity_24h_enabled,
                            streak_enabled = excluded.streak_enabled,
                            weekly_plan_due_enabled = excluded.weekly_plan_due_enabled,
                            updated_at = CURRENT_TIMESTAMP
                        ''',
                        (
                            normalized_payload['user_id'],
                            normalized_payload['in_app_enabled'],
                            normalized_payload['inactivity_24h_enabled'],
                            normalized_payload['streak_enabled'],
                            normalized_payload['weekly_plan_due_enabled'],
                        )
                    )
                    conn.commit()
                    return {
                        'success': True,
                        'settings': self.get_notification_settings(normalized_user_id),
                    }
        except Exception as e:
            print(f"upsert_notification_settings failed: {e}")
            return {'success': False, 'error': str(e), 'settings': None}

    @staticmethod
    def _safe_json_loads(value, default):
        if not value:
            return default
        try:
            return json.loads(value)
        except Exception:
            return default

    @staticmethod
    def _truncate_text(value, limit=120):
        text = str(value or '').strip()
        if len(text) <= limit:
            return text
        return f"{text[:limit].rstrip()}..."

    def _serialize_assistant_conversation(self, row):
        if not row:
            return None
        item = dict(row)
        item['archived'] = bool(item.get('archived'))
        item['message_count'] = int(item.get('message_count') or 0)
        return item

    def _serialize_assistant_message(self, row):
        if not row:
            return None
        item = dict(row)
        item['citations'] = self._safe_json_loads(item.pop('citations_json', None), [])
        item['retrieval_meta'] = self._safe_json_loads(item.pop('retrieval_meta_json', None), {})
        return item

    def _collapse_empty_assistant_conversations(self, conn, user_id='default'):
        cursor = conn.cursor()
        normalized_user_id = str(user_id or 'default').strip() or 'default'
        cursor.execute(
            '''
            SELECT
                c.*,
                COUNT(m.id) AS message_count
            FROM assistant_conversations c
            LEFT JOIN assistant_messages m
                ON m.conversation_id = c.conversation_id
            WHERE c.user_id = ? AND c.archived = 0
            GROUP BY c.conversation_id
            HAVING COUNT(m.id) = 0
            ORDER BY c.updated_at DESC, c.created_at DESC
            ''',
            (normalized_user_id,)
        )
        rows = cursor.fetchall()
        if not rows:
            return None

        keeper = rows[0]
        duplicate_ids = [
            str(dict(row).get('conversation_id') or '').strip()
            for row in rows[1:]
            if str(dict(row).get('conversation_id') or '').strip()
        ]
        if duplicate_ids:
            placeholders = ', '.join('?' for _ in duplicate_ids)
            cursor.execute(
                f'''
                UPDATE assistant_conversations
                SET archived = 1, updated_at = CURRENT_TIMESTAMP
                WHERE conversation_id IN ({placeholders})
                ''',
                duplicate_ids
            )
        return self._serialize_assistant_conversation(keeper)

    def create_assistant_conversation(self, user_id='default', title='新对话', conversation_id=None):
        with self._lock:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    normalized_user_id = str(user_id or 'default').strip() or 'default'
                    normalized_title = self._truncate_text(title or '新对话', limit=80) or '新对话'

                    existing_empty = self._collapse_empty_assistant_conversations(conn, normalized_user_id)
                    if existing_empty:
                        return existing_empty

                    normalized_conversation_id = str(conversation_id or '').strip()
                    if not normalized_conversation_id:
                        normalized_conversation_id = f"assistant_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

                    cursor.execute(
                        '''
                        INSERT INTO assistant_conversations
                        (conversation_id, user_id, title, last_message_preview)
                        VALUES (?, ?, ?, ?)
                        ''',
                        (normalized_conversation_id, normalized_user_id, normalized_title, '')
                    )
                    conn.commit()

                    cursor.execute(
                        '''
                        SELECT c.*, 0 AS message_count
                        FROM assistant_conversations c
                        WHERE c.conversation_id = ?
                        LIMIT 1
                        ''',
                        (normalized_conversation_id,)
                    )
                    row = cursor.fetchone()
                    return self._serialize_assistant_conversation(row)
            except Exception as e:
                print(f"create_assistant_conversation failed: {e}")
                return None

    def list_assistant_conversations(self, user_id='default', limit=50, offset=0, include_archived=False):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                normalized_user_id = str(user_id or 'default').strip() or 'default'
                safe_limit = max(1, min(int(limit or 50), 200))
                safe_offset = max(0, int(offset or 0))

                if not include_archived:
                    self._collapse_empty_assistant_conversations(conn, normalized_user_id)

                query = '''
                    SELECT
                        c.*,
                        COUNT(m.id) AS message_count
                    FROM assistant_conversations c
                    LEFT JOIN assistant_messages m
                        ON m.conversation_id = c.conversation_id
                    WHERE c.user_id = ?
                '''
                params = [normalized_user_id]
                if not include_archived:
                    query += ' AND c.archived = 0'

                query += '''
                    GROUP BY c.conversation_id
                    ORDER BY c.updated_at DESC, c.created_at DESC
                    LIMIT ? OFFSET ?
                '''
                params.extend([safe_limit, safe_offset])
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [self._serialize_assistant_conversation(row) for row in rows]
        except Exception as e:
            print(f"list_assistant_conversations failed: {e}")
            return []

    def get_assistant_conversation(self, conversation_id, user_id=None):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = '''
                    SELECT
                        c.*,
                        COUNT(m.id) AS message_count
                    FROM assistant_conversations c
                    LEFT JOIN assistant_messages m
                        ON m.conversation_id = c.conversation_id
                    WHERE c.conversation_id = ?
                '''
                params = [str(conversation_id or '').strip()]
                if user_id:
                    query += ' AND c.user_id = ?'
                    params.append(str(user_id).strip())
                query += ' GROUP BY c.conversation_id LIMIT 1'
                cursor.execute(query, params)
                row = cursor.fetchone()
                return self._serialize_assistant_conversation(row)
        except Exception as e:
            print(f"get_assistant_conversation failed: {e}")
            return None

    def update_assistant_conversation(self, conversation_id, *, title=None, last_message_preview=None, archived=None):
        with self._lock:
            try:
                updates = []
                params = []

                if title is not None:
                    updates.append('title = ?')
                    params.append(self._truncate_text(title or '新对话', limit=80) or '新对话')
                if last_message_preview is not None:
                    updates.append('last_message_preview = ?')
                    params.append(self._truncate_text(last_message_preview, limit=120))
                if archived is not None:
                    updates.append('archived = ?')
                    params.append(1 if archived else 0)

                updates.append('updated_at = CURRENT_TIMESTAMP')
                params.append(str(conversation_id or '').strip())

                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        f'''
                        UPDATE assistant_conversations
                        SET {', '.join(updates)}
                        WHERE conversation_id = ?
                        ''',
                        params
                    )
                    conn.commit()
                    return cursor.rowcount > 0
            except Exception as e:
                print(f"update_assistant_conversation failed: {e}")
                return False

    def delete_assistant_conversation(self, conversation_id, user_id=None):
        """Soft-delete an assistant conversation by archiving it."""
        with self._lock:
            try:
                normalized_conversation_id = str(conversation_id or '').strip()
                if not normalized_conversation_id:
                    return False
                normalized_user_id = str(user_id or '').strip()

                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    query = '''
                        UPDATE assistant_conversations
                        SET archived = 1, updated_at = CURRENT_TIMESTAMP
                        WHERE conversation_id = ?
                    '''
                    params = [normalized_conversation_id]
                    if normalized_user_id:
                        query += ' AND user_id = ?'
                        params.append(normalized_user_id)

                    cursor.execute(query, params)
                    conn.commit()
                    return cursor.rowcount > 0
            except Exception as e:
                print(f"delete_assistant_conversation failed: {e}")
                return False

    def append_assistant_message(
        self,
        conversation_id,
        *,
        role,
        content,
        message_type='text',
        citations=None,
        answer_mode=None,
        retrieval_meta=None,
        message_id=None,
    ):
        with self._lock:
            try:
                normalized_conversation_id = str(conversation_id or '').strip()
                normalized_role = str(role or '').strip().lower() or 'assistant'
                normalized_content = str(content or '').strip()
                if not normalized_conversation_id or not normalized_content:
                    return None

                normalized_message_id = str(message_id or '').strip()
                if not normalized_message_id:
                    normalized_message_id = f"msg_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        '''
                        INSERT INTO assistant_messages
                        (message_id, conversation_id, role, content, message_type, citations_json, answer_mode, retrieval_meta_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                        (
                            normalized_message_id,
                            normalized_conversation_id,
                            normalized_role,
                            normalized_content,
                            str(message_type or 'text').strip() or 'text',
                            json.dumps(citations or [], ensure_ascii=False),
                            str(answer_mode or '').strip() or None,
                            json.dumps(retrieval_meta or {}, ensure_ascii=False),
                        )
                    )

                    cursor.execute(
                        '''
                        UPDATE assistant_conversations
                        SET last_message_preview = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE conversation_id = ?
                        ''',
                        (self._truncate_text(normalized_content, limit=120), normalized_conversation_id)
                    )
                    conn.commit()

                    cursor.execute(
                        '''
                        SELECT *
                        FROM assistant_messages
                        WHERE message_id = ?
                        LIMIT 1
                        ''',
                        (normalized_message_id,)
                    )
                    row = cursor.fetchone()
                    return self._serialize_assistant_message(row)
            except Exception as e:
                print(f"append_assistant_message failed: {e}")
                return None

    def get_assistant_messages(self, conversation_id, user_id=None, limit=200):
        try:
            normalized_conversation_id = str(conversation_id or '').strip()
            safe_limit = max(1, min(int(limit or 200), 500))
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if user_id:
                    cursor.execute(
                        '''
                        SELECT m.*
                        FROM assistant_messages m
                        INNER JOIN assistant_conversations c
                            ON c.conversation_id = m.conversation_id
                        WHERE m.conversation_id = ? AND c.user_id = ?
                        ORDER BY m.created_at ASC, m.id ASC
                        LIMIT ?
                        ''',
                        (normalized_conversation_id, str(user_id).strip(), safe_limit)
                    )
                else:
                    cursor.execute(
                        '''
                        SELECT *
                        FROM assistant_messages
                        WHERE conversation_id = ?
                        ORDER BY created_at ASC, id ASC
                        LIMIT ?
                        ''',
                        (normalized_conversation_id, safe_limit)
                    )
                rows = cursor.fetchall()
                return [self._serialize_assistant_message(row) for row in rows]
        except Exception as e:
            print(f"get_assistant_messages failed: {e}")
            return []

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

    @staticmethod
    def _extract_json_records_from_markdown(path: Path):
        text = path.read_text(encoding='utf-8')
        decoder = json.JSONDecoder()
        records = []
        cursor = 0

        while cursor < len(text):
            start = text.find('{', cursor)
            if start == -1:
                break

            try:
                record, offset = decoder.raw_decode(text[start:])
            except json.JSONDecodeError:
                cursor = start + 1
                continue

            if isinstance(record, dict):
                records.append(record)
            elif isinstance(record, list):
                records.extend(item for item in record if isinstance(item, dict))

            cursor = start + offset

        if records:
            structured_records = []
            for item in records:
                if not isinstance(item, dict):
                    continue
                question = str(
                    item.get('question')
                    or item.get('title')
                    or item.get('content')
                    or ''
                ).strip()
                if not question:
                    continue
                structured_records.append(item)
            if structured_records:
                return structured_records

        return DatabaseManager._extract_question_records_from_plain_markdown(path, text)

    @staticmethod
    def _extract_question_candidates_from_plain_markdown(text: str):
        chinese_cues = (
            '为什么',
            '如何',
            '怎么',
            '是什么',
            '区别',
            '哪些',
            '哪种',
            '原理',
            '流程',
            '思路',
            '设计',
            '优化',
        )
        english_cues = ('why', 'how', 'what', 'difference', 'compare', 'design', 'explain')

        candidates = []
        for raw_line in (text or '').splitlines():
            line = str(raw_line or '').strip()
            if not line or line.startswith('```'):
                continue

            line = re.sub(r'^[#>\-\*\+\s]+', '', line)
            line = re.sub(r'^\d+[\.\)\、]\s*', '', line)
            line = re.sub(r'^[（(]?\d+[）)]\s*', '', line)
            line = re.sub(r'\s+', ' ', line).strip(' \t-_')
            if len(line) < 8 or len(line) > 160:
                continue

            lower = line.lower()
            has_question_mark = ('?' in line) or ('？' in line)
            has_chinese_cue = any(cue in line for cue in chinese_cues)
            has_english_cue = any(cue in lower for cue in english_cues)
            if not (has_question_mark or has_chinese_cue or has_english_cue):
                continue

            cleaned = line.rstrip('。；;,，、')
            if cleaned:
                candidates.append(cleaned)

        deduped = []
        seen = set()
        for question in candidates:
            key = question.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(question)
        return deduped

    @staticmethod
    def _infer_role_from_markdown_path(path: Path):
        stem = str(path.stem or '').strip().lower()
        if any(token in stem for token in ('frontend', 'qianduan', 'fe')):
            return '前端工程师'
        if any(token in stem for token in ('java', 'backend')):
            return 'Java后端工程师'
        if any(token in stem for token in ('test', 'qa', 'ceshi', '测试')):
            return '软件测试工程师'
        if any(token in stem for token in ('chanpin', 'product', 'pm')):
            return '产品经理'
        if any(token in stem for token in ('agent', '智能体', 'zhinengti')):
            return 'Agent开发工程师'
        if any(token in stem for token in ('algorithm', 'mianjing')):
            return '算法工程师'
        return '通用岗位'

    @staticmethod
    def _extract_question_records_from_plain_markdown(path: Path, text: str):
        questions = DatabaseManager._extract_question_candidates_from_plain_markdown(text)
        if not questions:
            return []

        role = DatabaseManager._infer_role_from_markdown_path(path)
        records = []
        for index, question in enumerate(questions, start=1):
            records.append({
                'id': f"{path.stem}_plain_{index:03d}",
                'role': role,
                'position': role,
                'question': question,
                'category': '面经整理',
                'difficulty': 'medium',
                'question_type': '经验问答',
                'round_type': 'technical',
                'keywords': [],
                'answer_summary': '',
                'source': str(path.name),
                'source_type': 'auto_markdown_extraction',
            })
        return records

    @staticmethod
    def _normalize_question_difficulty(value):
        normalized = str(value or '').strip().lower()
        mapping = {
            '简单': 'easy',
            '初级': 'easy',
            'easy': 'easy',
            '中等': 'medium',
            '普通': 'medium',
            'medium': 'medium',
            '困难': 'hard',
            '高级': 'hard',
            'hard': 'hard',
        }
        return mapping.get(normalized, 'medium')

    @staticmethod
    def _normalize_question_category(value, fallback: str = '未分类'):
        def _pick_candidate(raw):
            if isinstance(raw, (list, tuple, set)):
                for item in raw:
                    text = str(item or '').strip()
                    if text:
                        return text
                return ''
            if isinstance(raw, dict):
                return str(
                    raw.get('label')
                    or raw.get('name')
                    or raw.get('category')
                    or ''
                ).strip()
            return str(raw or '').strip()

        candidate = _pick_candidate(value)
        if not candidate:
            candidate = _pick_candidate(fallback)

        candidate = candidate.replace('\u3000', ' ')
        candidate = re.sub(r'[\u200b-\u200d\ufeff]', '', candidate)
        candidate = re.sub(r'\s+', ' ', candidate).strip(' -_')
        return candidate or '未分类'

    @staticmethod
    def _infer_position_from_role(role_text, file_stem):
        role = str(role_text or '').strip().lower()
        stem = str(file_stem or '').strip().lower()
        merged = f'{role} {stem}'

        if 'java' in merged and ('后端' in merged or 'backend' in merged):
            return 'java_backend'
        if 'agent_developer' in merged or 'agent开发' in merged or 'agent' in merged or '智能体' in merged:
            return 'agent_developer'
        if '算法' in merged or 'algorithm' in merged:
            return 'algorithm'
        if '前端' in merged or 'frontend' in merged or 'qianduan' in merged:
            return 'frontend'
        if (
            'test_engineer' in merged
            or 'software_test' in merged
            or 'qa' in merged
            or '测试' in merged
            or '软件测试' in merged
            or 'fullstack' in merged
            or '全栈' in merged
        ):
            return 'test_engineer'
        if ('data' in merged and 'engineer' in merged) or '数据工程' in merged:
            return 'agent_developer'
        if 'devops' in merged:
            return 'devops'
        if '产品' in merged or ('product' in merged and 'manager' in merged) or 'chanpin' in merged:
            return 'product_manager'

        return stem or 'unknown'

    def _load_question_bank_from_interview_knowledge(
        self,
        round_type: str = None,
        position: str = None,
        difficulty: str = None
    ):
        """
        从 backend/interview_knowledge 目录加载题库。
        支持 .md / .json / .jsonl，md 中按 JSON 对象块解析。
        """
        backend_root = Path(__file__).resolve().parents[1]
        knowledge_dirs = [
            backend_root / 'interview_knowledge',
            backend_root / 'basic_knowledge',
        ]
        knowledge_dirs = [item for item in knowledge_dirs if item.exists() and item.is_dir()]
        if not knowledge_dirs:
            return []

        round_type_filter = str(round_type or '').strip().lower()
        position_filter = str(position or '').strip().lower()
        if position_filter in {'data_engineer', '数据工程师', 'agent开发', 'agent开发工程师'}:
            position_filter = 'agent_developer'
        difficulty_filter = self._normalize_question_difficulty(difficulty) if difficulty else ''

        all_records = []
        supported_suffixes = {'.md', '.json', '.jsonl'}
        files = []
        for knowledge_dir in knowledge_dirs:
            files.extend(
                [
                    item for item in sorted(knowledge_dir.iterdir())
                    if item.is_file() and item.suffix.lower() in supported_suffixes
                ]
            )

        for file_path in files:
            try:
                suffix = file_path.suffix.lower()
                parsed_records = []

                if suffix == '.md':
                    parsed_records = self._extract_json_records_from_markdown(file_path)
                elif suffix == '.jsonl':
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            obj = json.loads(line)
                            if isinstance(obj, dict):
                                parsed_records.append(obj)
                            elif isinstance(obj, list):
                                parsed_records.extend(item for item in obj if isinstance(item, dict))
                else:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        if isinstance(data.get('questions'), list):
                            parsed_records = [item for item in data['questions'] if isinstance(item, dict)]
                        else:
                            parsed_records = [data]
                    elif isinstance(data, list):
                        parsed_records = [item for item in data if isinstance(item, dict)]

                all_records.extend((file_path, idx, record) for idx, record in enumerate(parsed_records, start=1))
            except Exception as e:
                print(f"⚠️  读取知识库文件失败（已跳过）: {file_path} - {e}")

        question_bank = []
        seen = set()

        for file_path, index, record in all_records:
            question = str(
                record.get('question')
                or record.get('title')
                or record.get('content')
                or ''
            ).strip()
            if not question:
                continue

            role = str(record.get('role') or record.get('position') or '').strip()
            normalized_round_type = str(record.get('round_type') or 'technical').strip().lower()
            normalized_position = self._infer_position_from_role(role, file_path.stem).lower()
            normalized_difficulty = self._normalize_question_difficulty(record.get('difficulty'))

            if round_type_filter and normalized_round_type != round_type_filter:
                continue
            if position_filter and normalized_position != position_filter:
                continue
            if difficulty_filter and normalized_difficulty != difficulty_filter:
                continue

            dedupe_key = (question.lower(), normalized_round_type, normalized_position)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            question_bank.append({
                'id': str(record.get('id') or f"{file_path.stem}-{index}"),
                'question': question,
                'category': self._normalize_question_category(
                    record.get('category')
                    or record.get('subcategory')
                    or record.get('question_type'),
                    fallback=normalized_round_type,
                ),
                'round_type': normalized_round_type,
                'position': normalized_position,
                'difficulty': normalized_difficulty,
                'frequency': str(record.get('frequency') or '').strip(),
                'description': str(record.get('answer_summary') or '').strip(),
                'created_at': '',
                'source': str(file_path.name),
            })

        return question_bank

    def get_question_bank(
        self,
        round_type: str = None,
        position: str = None,
        difficulty: str = None
    ):
        """
        从数据库拉取题库：
        1) 优先 interview_rounds.questions(JSON)
        2) 若为空，回退到 interview_dialogues.question 聚合

        Args:
            round_type: 轮次类型过滤（可选）
            position: 岗位过滤（可选）
            difficulty: 难度过滤（可选）

        Returns:
            list: 题目列表（按 created_at/id 倒序去重）
        """
        try:
            # 优先使用 backend/interview_knowledge 目录作为题库来源
            knowledge_question_bank = self._load_question_bank_from_interview_knowledge(
                round_type=round_type,
                position=position,
                difficulty=difficulty,
            )
            if knowledge_question_bank:
                return knowledge_question_bank

            conditions = []
            params = []

            if round_type:
                conditions.append('round_type = ?')
                params.append(round_type)
            if position:
                conditions.append('position = ?')
                params.append(position)
            if difficulty:
                conditions.append('difficulty = ?')
                params.append(difficulty)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ''

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    SELECT id, round_type, position, difficulty, questions, description, created_at
                    FROM interview_rounds
                    {where_clause}
                    ORDER BY datetime(created_at) DESC, id DESC
                ''', params)
                rows = cursor.fetchall()

            question_bank = []
            seen = set()

            def _safe_text(value):
                return str(value or '').strip()

            def _normalize_question_entry(entry):
                if isinstance(entry, str):
                    text = _safe_text(entry)
                    return {
                        'text': text,
                        'category': '',
                        'subcategory': '',
                        'difficulty': '',
                        'frequency': '',
                        'source_question_id': '',
                    } if text else None

                if isinstance(entry, dict):
                    text = _safe_text(
                        entry.get('title')
                        or entry.get('question')
                        or entry.get('content')
                        or entry.get('text')
                    )
                    if not text:
                        return None
                    return {
                        'text': text,
                        'category': _safe_text(entry.get('category') or entry.get('dimension')),
                        'subcategory': _safe_text(entry.get('subcategory')),
                        'difficulty': _safe_text(entry.get('difficulty')),
                        'frequency': _safe_text(entry.get('frequency') or entry.get('frequency_label')),
                        'source_question_id': _safe_text(entry.get('id') or entry.get('question_id')),
                    }

                return None

            for row in rows:
                questions_raw = row['questions']
                if not questions_raw:
                    continue

                parsed_questions = []
                if isinstance(questions_raw, str):
                    try:
                        parsed_questions = json.loads(questions_raw)
                    except Exception:
                        parsed_questions = []
                elif isinstance(questions_raw, (list, tuple)):
                    parsed_questions = list(questions_raw)

                if isinstance(parsed_questions, dict):
                    parsed_questions = [parsed_questions]

                if not isinstance(parsed_questions, list):
                    continue

                for index, item in enumerate(parsed_questions):
                    normalized = _normalize_question_entry(item)
                    if not normalized:
                        continue

                    question_text = normalized['text']
                    dedupe_key = (
                        question_text.lower(),
                        _safe_text(row['round_type']).lower(),
                        _safe_text(row['position']).lower(),
                    )
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)

                    bank_id = normalized['source_question_id'] or f"{row['id']}-{index + 1}"
                    row_difficulty = _safe_text(row['difficulty']).lower() or 'medium'
                    entry_difficulty = normalized['difficulty'].lower() or row_difficulty

                    question_bank.append({
                        'id': bank_id,
                        'question': question_text,
                        'category': self._normalize_question_category(
                            normalized.get('category') or normalized.get('subcategory'),
                            fallback=_safe_text(row['round_type']),
                        ),
                        'round_type': _safe_text(row['round_type']),
                        'position': _safe_text(row['position']),
                        'difficulty': entry_difficulty,
                        'frequency': normalized['frequency'] or '',
                        'description': _safe_text(row['description']),
                        'created_at': _safe_text(row['created_at']),
                    })

            if question_bank:
                return question_bank

            # 回退：直接使用历史对话中的题目作为题库
            if position:
                # interview_dialogues 当前无岗位字段，带岗位过滤时不做回退
                return []

            normalized_difficulty = str(difficulty or '').strip().lower()
            if normalized_difficulty and normalized_difficulty not in {'medium', 'normal', '中等'}:
                # interview_dialogues 无难度字段，仅支持默认中等
                return []

            dialogue_conditions = ["question IS NOT NULL", "TRIM(question) <> ''"]
            dialogue_params = []
            if round_type:
                dialogue_conditions.append('round_type = ?')
                dialogue_params.append(round_type)
            dialogue_where = f"WHERE {' AND '.join(dialogue_conditions)}"

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    SELECT
                        round_type,
                        question,
                        COUNT(*) AS frequency_count,
                        MAX(created_at) AS created_at
                    FROM interview_dialogues
                    {dialogue_where}
                    GROUP BY round_type, question
                    ORDER BY datetime(created_at) DESC
                ''', dialogue_params)
                dialogue_rows = cursor.fetchall()

            if not dialogue_rows:
                return []

            fallback_bank = []

            def _frequency_label(count):
                if count >= 5:
                    return 'Very High'
                if count >= 3:
                    return 'High'
                if count >= 2:
                    return 'Medium'
                return 'Low'

            for index, row in enumerate(dialogue_rows):
                text = _safe_text(row['question'])
                if not text:
                    continue
                fallback_bank.append({
                    'id': f"dialogue-{index + 1}",
                    'question': text,
                    'category': self._normalize_question_category(_safe_text(row['round_type']), fallback='未分类'),
                    'round_type': _safe_text(row['round_type']),
                    'position': '',
                    'difficulty': 'medium',
                    'frequency': _frequency_label(int(row['frequency_count'] or 0)),
                    'description': 'from interview_dialogues',
                    'created_at': _safe_text(row['created_at']),
                })

            return fallback_bank

        except Exception as e:
            print(f"✗ 查询题库失败：{e}")
            return []

    def get_question_bank_facets(self):
        """
        获取题库筛选维度（轮次、岗位、难度）。

        Returns:
            dict: {'round_types': [...], 'positions': [...], 'difficulties': [...]}
        """
        try:
            knowledge_question_bank = self._load_question_bank_from_interview_knowledge()
            if knowledge_question_bank:
                return {
                    'round_types': sorted({
                        str(item.get('round_type', '')).strip()
                        for item in knowledge_question_bank
                        if str(item.get('round_type', '')).strip()
                    }),
                    'positions': sorted({
                        str(item.get('position', '')).strip()
                        for item in knowledge_question_bank
                        if str(item.get('position', '')).strip()
                    }),
                    'difficulties': sorted({
                        str(item.get('difficulty', '')).strip()
                        for item in knowledge_question_bank
                        if str(item.get('difficulty', '')).strip()
                    }),
                }

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT DISTINCT round_type, position, difficulty
                    FROM interview_rounds
                ''')
                round_rows = cursor.fetchall()

                cursor.execute('''
                    SELECT DISTINCT round_type
                    FROM interview_dialogues
                    WHERE round_type IS NOT NULL AND TRIM(round_type) <> ''
                ''')
                dialogue_round_rows = cursor.fetchall()

                cursor.execute('''
                    SELECT COUNT(*) AS total
                    FROM interview_dialogues
                    WHERE question IS NOT NULL AND TRIM(question) <> ''
                ''')
                dialogue_question_total = int(cursor.fetchone()['total'] or 0)

            round_types = sorted(
                {
                    str(row['round_type']).strip()
                    for row in round_rows
                    if str(row['round_type']).strip()
                }.union(
                    {
                        str(row['round_type']).strip()
                        for row in dialogue_round_rows
                        if str(row['round_type']).strip()
                    }
                )
            )
            positions = sorted({str(row['position']).strip() for row in round_rows if str(row['position']).strip()})
            difficulties = sorted({str(row['difficulty']).strip() for row in round_rows if str(row['difficulty']).strip()})
            if dialogue_question_total > 0 and 'medium' not in {item.lower() for item in difficulties}:
                difficulties.append('medium')
                difficulties = sorted(difficulties)

            return {
                'round_types': round_types,
                'positions': positions,
                'difficulties': difficulties,
            }
        except Exception as e:
            print(f"✗ 查询题库筛选维度失败：{e}")
            return {
                'round_types': [],
                'positions': [],
                'difficulties': [],
            }

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
                (interview_id, turn_id, round_type, question, answer, llm_feedback, score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                dialogue_data['interview_id'],
                dialogue_data.get('turn_id'),
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

    def save_or_update_interview_asset(self, payload):
        """保存或更新面试视频资产（interview_id 幂等）。"""
        columns = [
            'interview_id',
            'upload_id',
            'storage_key',
            'video_url',
            'local_path',
            'duration_ms',
            'codec',
            'status',
            'metadata_json',
        ]
        values = [payload.get(col) for col in columns]
        placeholders = ', '.join(['?'] * len(columns))
        update_cols = [col for col in columns if col != 'interview_id']
        update_set = ', '.join([f"{col}=excluded.{col}" for col in update_cols] + ["updated_at=CURRENT_TIMESTAMP"])

        sql = f'''
            INSERT INTO interview_assets ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(interview_id)
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
                        SELECT id FROM interview_assets WHERE interview_id = ? LIMIT 1
                        ''',
                        (payload.get('interview_id', ''),)
                    )
                    row = cursor.fetchone()
                    return {
                        'success': True,
                        'id': int(row['id']) if row and row['id'] is not None else 0,
                    }
            except Exception as e:
                print(f"✗ 保存视频资产失败：{e}")
                return {'success': False, 'error': str(e)}

    def get_interview_asset(self, interview_id: str):
        """获取单场面试视频资产。"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT * FROM interview_assets
                    WHERE interview_id = ?
                    ORDER BY datetime(updated_at) DESC, id DESC
                    LIMIT 1
                    ''',
                    (interview_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"✗ 查询视频资产失败：{e}")
            return None

    def save_or_update_turn_timeline(self, payload):
        """保存或更新 turn 级时间锚点。"""
        columns = [
            'interview_id',
            'turn_id',
            'question_start_ms',
            'question_end_ms',
            'answer_start_ms',
            'answer_end_ms',
            'latency_ms',
            'source',
        ]
        values = [payload.get(col) for col in columns]
        placeholders = ', '.join(['?'] * len(columns))
        update_cols = [col for col in columns if col not in ('interview_id', 'turn_id')]
        # 允许按阶段增量写入（先 question，再 answer），避免后写覆盖前写的非空字段。
        update_set = ', '.join(
            [f"{col}=COALESCE(excluded.{col}, {col})" for col in update_cols] +
            ["updated_at=CURRENT_TIMESTAMP"]
        )
        sql = f'''
            INSERT INTO interview_turn_timeline ({', '.join(columns)})
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
                    return {'success': True}
            except Exception as e:
                print(f"✗ 保存 turn 时间轴失败：{e}")
                return {'success': False, 'error': str(e)}

    def get_interview_turn_timelines(self, interview_id: str):
        """获取单场面试 turn 时间轴。"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT * FROM interview_turn_timeline
                    WHERE interview_id = ?
                    ORDER BY COALESCE(answer_start_ms, question_start_ms, 0) ASC, id ASC
                    ''',
                    (interview_id,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"✗ 查询 turn 时间轴失败：{e}")
            return []

    def replace_timeline_tags(self, interview_id: str, tags):
        """覆盖写入时间轴标签。"""
        with self._lock:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        'DELETE FROM interview_timeline_tags WHERE interview_id = ?',
                        (interview_id,)
                    )
                    for item in tags or []:
                        cursor.execute(
                            '''
                            INSERT INTO interview_timeline_tags
                            (interview_id, turn_id, tag_type, start_ms, end_ms, reason, confidence, evidence_json, source)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''',
                            (
                                interview_id,
                                item.get('turn_id'),
                                item.get('tag_type', ''),
                                item.get('start_ms', 0),
                                item.get('end_ms', 0),
                                item.get('reason', ''),
                                item.get('confidence', 0.0),
                                item.get('evidence_json', ''),
                                item.get('source', 'review_service'),
                            )
                        )
                    conn.commit()
                    return {'success': True, 'count': len(tags or [])}
            except Exception as e:
                print(f"✗ 覆盖时间轴标签失败：{e}")
                return {'success': False, 'error': str(e)}

    def get_timeline_tags(self, interview_id: str):
        """读取单场面试时间轴标签。"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT * FROM interview_timeline_tags
                    WHERE interview_id = ?
                    ORDER BY start_ms ASC, id ASC
                    ''',
                    (interview_id,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"✗ 查询时间轴标签失败：{e}")
            return []

    def save_or_update_deep_audit(self, payload):
        """保存或更新深度技术诊断（interview_id 幂等）。"""
        columns = [
            'interview_id',
            'fact_checks_json',
            'dimension_gaps_json',
            'round_diagnosis_json',
            'version',
        ]
        values = [payload.get(col) for col in columns]
        placeholders = ', '.join(['?'] * len(columns))
        update_cols = [col for col in columns if col != 'interview_id']
        update_set = ', '.join([f"{col}=excluded.{col}" for col in update_cols] + ["updated_at=CURRENT_TIMESTAMP"])
        sql = f'''
            INSERT INTO interview_deep_audits ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(interview_id)
            DO UPDATE SET {update_set}
        '''
        with self._lock:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(sql, values)
                    conn.commit()
                    return {'success': True}
            except Exception as e:
                print(f"✗ 保存深度技术诊断失败：{e}")
                return {'success': False, 'error': str(e)}

    def get_deep_audit(self, interview_id: str):
        """读取单场深度技术诊断。"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT * FROM interview_deep_audits
                    WHERE interview_id = ?
                    LIMIT 1
                    ''',
                    (interview_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"✗ 查询深度技术诊断失败：{e}")
            return None

    def replace_shadow_answers(self, interview_id: str, records, version: str = 'v1'):
        """覆盖写入影子回答。"""
        with self._lock:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        'DELETE FROM interview_shadow_answers WHERE interview_id = ? AND version = ?',
                        (interview_id, version)
                    )
                    for item in records or []:
                        cursor.execute(
                            '''
                            INSERT INTO interview_shadow_answers
                            (interview_id, turn_id, question, original_answer, shadow_answer, why_better, resume_alignment_json, version)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ''',
                            (
                                interview_id,
                                item.get('turn_id', ''),
                                item.get('question', ''),
                                item.get('original_answer', ''),
                                item.get('shadow_answer', ''),
                                item.get('why_better', ''),
                                item.get('resume_alignment_json', ''),
                                version,
                            )
                        )
                    conn.commit()
                    return {'success': True, 'count': len(records or [])}
            except Exception as e:
                print(f"✗ 覆盖影子回答失败：{e}")
                return {'success': False, 'error': str(e)}

    def get_shadow_answers(self, interview_id: str, version: str = None):
        """读取影子回答列表。"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if version:
                    cursor.execute(
                        '''
                        SELECT * FROM interview_shadow_answers
                        WHERE interview_id = ? AND version = ?
                        ORDER BY datetime(created_at) ASC, id ASC
                        ''',
                        (interview_id, version)
                    )
                else:
                    cursor.execute(
                        '''
                        SELECT * FROM interview_shadow_answers
                        WHERE interview_id = ?
                        ORDER BY datetime(created_at) ASC, id ASC
                        ''',
                        (interview_id,)
                    )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"✗ 查询影子回答失败：{e}")
            return []

    def save_or_update_visual_metrics(self, payload):
        """保存或更新可视化矩阵数据。"""
        columns = [
            'interview_id',
            'latency_matrix_json',
            'keyword_coverage_json',
            'speech_tone_json',
            'radar_json',
            'heatmap_json',
            'version',
        ]
        values = [payload.get(col) for col in columns]
        placeholders = ', '.join(['?'] * len(columns))
        update_cols = [col for col in columns if col != 'interview_id']
        update_set = ', '.join([f"{col}=excluded.{col}" for col in update_cols] + ["updated_at=CURRENT_TIMESTAMP"])
        sql = f'''
            INSERT INTO interview_visual_metrics ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(interview_id)
            DO UPDATE SET {update_set}
        '''
        with self._lock:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(sql, values)
                    conn.commit()
                    return {'success': True}
            except Exception as e:
                print(f"✗ 保存可视化矩阵失败：{e}")
                return {'success': False, 'error': str(e)}

    def get_visual_metrics(self, interview_id: str):
        """读取可视化矩阵。"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT * FROM interview_visual_metrics
                    WHERE interview_id = ?
                    LIMIT 1
                    ''',
                    (interview_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"✗ 查询可视化矩阵失败：{e}")
            return None

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
            'text_layer_json', 'speech_layer_json', 'video_layer_json', 'fusion_json',
            'scoring_snapshot_json',
            'rubric_level', 'overall_score', 'confidence',
            'technical_accuracy_score', 'knowledge_depth_score', 'completeness_score',
            'logic_score', 'job_match_score',
            'authenticity_score', 'ownership_score', 'technical_depth_score', 'reflection_score',
            'architecture_reasoning_score', 'tradeoff_awareness_score', 'scalability_score',
            'clarity_score', 'relevance_score', 'self_awareness_score', 'communication_score',
            'confidence_score',
            'gaze_focus_score', 'posture_compliance_score', 'physiology_stability_score',
            'expression_naturalness_score', 'engagement_level_score',
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
                    # 兼容历史数据库：缺列时自动补齐，避免旧库写入失败。
                    self._ensure_interview_evaluations_schema(conn)
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
                        ORDER BY datetime(updated_at) DESC, id DESC
                        ''',
                        (interview_id, evaluation_version)
                    )
                else:
                    cursor.execute(
                        '''
                        SELECT *
                        FROM interview_evaluations
                        WHERE interview_id = ?
                        ORDER BY datetime(updated_at) DESC, id DESC
                        ''',
                        (interview_id,)
                    )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"✗ 查询评估记录失败：{e}")
            return []

    def get_recent_interview_evaluations_by_round(self, round_type: str, exclude_interview_id: str = None, limit: int = 300):
        """
        æŒ‰ round_type è¯»å–è¿‘æœŸ interview_evaluationsï¼Œç”¨äºŽåŠ¨æ€ round baseline æ ¡å‡†ã€‚
        """
        try:
            safe_limit = max(1, min(int(limit or 300), 1000))
            normalized_round = str(round_type or '').strip()
            normalized_exclude = str(exclude_interview_id or '').strip()
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if normalized_exclude:
                    cursor.execute(
                        '''
                        SELECT *
                        FROM interview_evaluations
                        WHERE round_type = ? AND interview_id != ?
                        ORDER BY datetime(updated_at) DESC, id DESC
                        LIMIT ?
                        ''',
                        (normalized_round, normalized_exclude, safe_limit)
                    )
                else:
                    cursor.execute(
                        '''
                        SELECT *
                        FROM interview_evaluations
                        WHERE round_type = ?
                        ORDER BY datetime(updated_at) DESC, id DESC
                        LIMIT ?
                        ''',
                        (normalized_round, safe_limit)
                    )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"é‰?è¯»å– round baseline è¯„ä¼°æ•°æ®å¤±è´¥: {e}")
            return []

    def log_evaluation_event(self, trace_id: str, interview_id: str, turn_id: str, event_type: str, status: str = '', duration_ms: float = None, payload=None):
        """记录评分链路事件。"""
        with self._lock:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        '''
                        INSERT INTO evaluation_traces
                        (trace_id, interview_id, turn_id, event_type, status, duration_ms, payload_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''',
                        (
                            str(trace_id or '').strip(),
                            str(interview_id or '').strip(),
                            str(turn_id or '').strip(),
                            str(event_type or '').strip(),
                            str(status or '').strip(),
                            duration_ms,
                            json.dumps(payload or {}, ensure_ascii=False),
                        )
                    )
                    conn.commit()
                    return {'success': True}
            except Exception as e:
                print(f"✗ 记录评分事件失败：{e}")
                return {'success': False, 'error': str(e)}

    def get_evaluation_traces(self, interview_id: str, turn_id: str = None):
        """读取评分链路事件。"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if turn_id:
                    cursor.execute(
                        '''
                        SELECT * FROM evaluation_traces
                        WHERE interview_id = ? AND turn_id = ?
                        ORDER BY datetime(created_at) ASC, id ASC
                        ''',
                        (interview_id, turn_id)
                    )
                else:
                    cursor.execute(
                        '''
                        SELECT * FROM evaluation_traces
                        WHERE interview_id = ?
                        ORDER BY datetime(created_at) ASC, id ASC
                        ''',
                        (interview_id,)
                    )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"✗ 查询评分事件失败：{e}")
            return []

    def get_turn_scorecard(self, interview_id: str, turn_id: str):
        """聚合单题评分卡。"""
        evaluation = None
        evaluations = self.get_interview_evaluations(interview_id=interview_id)
        for row in evaluations:
            if str((row or {}).get('turn_id') or '').strip() != str(turn_id or '').strip():
                continue
            status = str((row or {}).get('status') or '').strip().lower()
            if status in {'ok', 'partial_ok'}:
                evaluation = row
                break
            if evaluation is None:
                evaluation = row

        speech = None
        for row in self.get_speech_evaluations(interview_id=interview_id) or []:
            if str((row or {}).get('turn_id') or '').strip() == str(turn_id or '').strip():
                speech = row
                break

        traces = self.get_evaluation_traces(interview_id=interview_id, turn_id=turn_id)
        return {
            'interview_id': str(interview_id or '').strip(),
            'turn_id': str(turn_id or '').strip(),
            'evaluation': evaluation,
            'speech_evaluation': speech,
            'traces': traces,
        }

    def get_interview_structured_score_map(self, interview_ids):
        """
        批量获取面试结构化总分（按 turn 取最新评估记录后求平均）。
        优先使用 overall_score 列，若为 NULL 则尝试从 layer2_json 提取 overall_score_final。

        Returns:
            dict: {
                interview_id: {
                    'overall_score': float,
                    'scored_turns': int,
                    'score_source': 'structured_evaluation'
                }
            }
        """
        normalized_ids = [str(item).strip() for item in (interview_ids or []) if str(item).strip()]
        if not normalized_ids:
            return {}

        placeholders = ','.join(['?'] * len(normalized_ids))
        sql = f'''
            WITH ranked AS (
                SELECT
                    interview_id,
                    turn_id,
                    overall_score,
                    layer2_json,
                    status,
                    ROW_NUMBER() OVER (
                        PARTITION BY interview_id, turn_id
                        ORDER BY datetime(updated_at) DESC, id DESC
                    ) AS rn
                FROM interview_evaluations
                WHERE interview_id IN ({placeholders})
            )
            SELECT
                interview_id,
                turn_id,
                overall_score,
                layer2_json,
                status
            FROM ranked
            WHERE rn = 1
              AND status IN ('ok', 'partial_ok', 'skipped')
        '''

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, normalized_ids)
                rows = cursor.fetchall()

                interview_scores = {}
                for row in rows:
                    interview_id = str(row['interview_id'] or '').strip()
                    if not interview_id:
                        continue

                    score = None
                    raw_overall_score = row['overall_score']
                    if raw_overall_score is not None:
                        try:
                            score = float(raw_overall_score)
                        except (ValueError, TypeError):
                            pass

                    if score is None:
                        layer2_json_str = row['layer2_json']
                        if layer2_json_str:
                            try:
                                layer2 = json.loads(layer2_json_str)
                                final_score = layer2.get('overall_score_final')
                                if final_score is None:
                                    final_score = layer2.get('overall_score')
                                if final_score is not None:
                                    score = float(final_score)
                            except (json.JSONDecodeError, ValueError, TypeError):
                                pass

                    if score is not None:
                        interview_scores.setdefault(interview_id, []).append(score)

                result = {}
                for interview_id, scores in interview_scores.items():
                    if scores:
                        avg_score = round(sum(scores) / len(scores), 1)
                        result[interview_id] = {
                            'overall_score': avg_score,
                            'scored_turns': len(scores),
                            'score_source': 'structured_evaluation',
                        }
                return result
        except Exception as e:
            print(f"✗ 查询结构化总分失败：{e}")
            return {}

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

    def get_training_week_plan(self, user_id: str, week_start_date: str):
        """按用户与周起始日读取训练周计划。"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT *
                    FROM training_week_plans
                    WHERE user_id = ? AND week_start_date = ?
                    LIMIT 1
                    ''',
                    (str(user_id or '').strip(), str(week_start_date or '').strip())
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"✗ 查询训练周计划失败：{e}")
            return None

    def upsert_training_week_plan(self, plan_data):
        """创建或更新训练周计划（按 user_id + week_start_date 幂等）。"""
        columns = [
            'plan_id',
            'user_id',
            'week_start_date',
            'week_end_date',
            'target_position',
            'status',
            'source_summary_json',
        ]
        values = [plan_data.get(col) for col in columns]
        placeholders = ', '.join(['?'] * len(columns))
        sql = f'''
            INSERT INTO training_week_plans ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(user_id, week_start_date)
            DO UPDATE SET
                week_end_date = excluded.week_end_date,
                target_position = COALESCE(excluded.target_position, training_week_plans.target_position),
                status = COALESCE(excluded.status, training_week_plans.status),
                source_summary_json = COALESCE(excluded.source_summary_json, training_week_plans.source_summary_json),
                updated_at = CURRENT_TIMESTAMP
        '''

        try:
            with self._lock:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(sql, values)
                    conn.commit()
                    cursor.execute(
                        '''
                        SELECT *
                        FROM training_week_plans
                        WHERE user_id = ? AND week_start_date = ?
                        LIMIT 1
                        ''',
                        (
                            str(plan_data.get('user_id') or '').strip(),
                            str(plan_data.get('week_start_date') or '').strip(),
                        )
                    )
                    row = cursor.fetchone()
                    return {'success': True, 'plan': dict(row) if row else None}
        except Exception as e:
            print(f"✗ 写入训练周计划失败：{e}")
            return {'success': False, 'error': str(e), 'plan': None}

    def list_training_tasks_by_plan(self, plan_id: str):
        """按计划读取任务。"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT *
                    FROM training_tasks
                    WHERE plan_id = ?
                    ORDER BY priority ASC, datetime(created_at) ASC, id ASC
                    ''',
                    (str(plan_id or '').strip(),)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"✗ 查询训练任务失败：{e}")
            return []

    def get_training_task(self, task_id: str):
        """读取单个训练任务。"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT *
                    FROM training_tasks
                    WHERE task_id = ?
                    LIMIT 1
                    ''',
                    (str(task_id or '').strip(),)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"✗ 查询训练任务详情失败：{e}")
            return None

    def insert_training_tasks(self, task_items):
        """批量插入训练任务。"""
        if not task_items:
            return {'success': True, 'count': 0}

        columns = [
            'task_id',
            'plan_id',
            'user_id',
            'title',
            'round_type',
            'position',
            'difficulty',
            'focus_key',
            'focus_label',
            'goal_score',
            'status',
            'priority',
            'from_task_id',
            'due_at',
        ]
        placeholders = ', '.join(['?'] * len(columns))
        sql = f'''
            INSERT INTO training_tasks ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(task_id) DO NOTHING
        '''

        try:
            with self._lock:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    inserted = 0
                    for item in task_items:
                        values = [item.get(col) for col in columns]
                        cursor.execute(sql, values)
                        inserted += int(cursor.rowcount or 0)
                    conn.commit()
                    return {'success': True, 'count': inserted}
        except Exception as e:
            print(f"✗ 批量写入训练任务失败：{e}")
            return {'success': False, 'error': str(e), 'count': 0}

    def update_training_task_status(
        self,
        task_id: str,
        status: str,
        last_score=None,
        last_interview_id: str = None,
        set_training_started: bool = False,
        set_validation_started: bool = False,
    ):
        """更新训练任务状态及结果字段。"""
        normalized_task_id = str(task_id or '').strip()
        if not normalized_task_id:
            return {'success': False, 'error': 'invalid task_id'}

        updates = ['status = ?', 'updated_at = CURRENT_TIMESTAMP']
        params = [str(status or '').strip()]

        if last_score is not None:
            updates.append('last_score = ?')
            params.append(last_score)
        if last_interview_id is not None:
            updates.append('last_interview_id = ?')
            params.append(str(last_interview_id or '').strip())
        if set_training_started:
            updates.append('training_started_at = CURRENT_TIMESTAMP')
        if set_validation_started:
            updates.append('validation_started_at = CURRENT_TIMESTAMP')

        params.append(normalized_task_id)
        sql = f'''
            UPDATE training_tasks
            SET {', '.join(updates)}
            WHERE task_id = ?
        '''

        try:
            with self._lock:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(sql, params)
                    conn.commit()
                    if int(cursor.rowcount or 0) <= 0:
                        return {'success': False, 'error': 'task not found'}
                    return {'success': True}
        except Exception as e:
            print(f"✗ 更新训练任务状态失败：{e}")
            return {'success': False, 'error': str(e)}

    def create_training_task_attempt(self, attempt_data):
        """写入训练/验收尝试记录。"""
        columns = [
            'attempt_id',
            'task_id',
            'user_id',
            'attempt_type',
            'interview_id',
            'score',
            'passed',
            'notes',
        ]
        placeholders = ', '.join(['?'] * len(columns))
        values = [attempt_data.get(col) for col in columns]
        sql = f'''
            INSERT INTO training_task_attempts ({', '.join(columns)})
            VALUES ({placeholders})
        '''
        try:
            with self._lock:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(sql, values)
                    conn.commit()
                    return {'success': True}
        except Exception as e:
            print(f"✗ 写入训练尝试失败：{e}")
            return {'success': False, 'error': str(e)}

    def create_training_task_validation(self, validation_data):
        """写入验收结论记录。"""
        columns = [
            'validation_id',
            'task_id',
            'user_id',
            'validation_interview_id',
            'score',
            'passed',
            'decision',
        ]
        placeholders = ', '.join(['?'] * len(columns))
        values = [validation_data.get(col) for col in columns]
        sql = f'''
            INSERT INTO training_task_validations ({', '.join(columns)})
            VALUES ({placeholders})
        '''
        try:
            with self._lock:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(sql, values)
                    conn.commit()
                    return {'success': True}
        except Exception as e:
            print(f"✗ 写入验收结论失败：{e}")
            return {'success': False, 'error': str(e)}

    def get_training_plan_bundle(self, user_id: str, week_start_date: str):
        """读取周计划及任务列表。"""
        plan = self.get_training_week_plan(user_id=user_id, week_start_date=week_start_date)
        tasks = self.list_training_tasks_by_plan(str((plan or {}).get('plan_id') or '').strip()) if plan else []
        return {
            'plan': plan,
            'tasks': tasks,
        }


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
