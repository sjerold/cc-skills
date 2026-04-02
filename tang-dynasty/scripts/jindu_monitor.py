"""
进度监控器 - 监控任务执行进度和Agent健康度

功能：
- 读取各Agent状态
- 计算整体进度
- 检测健康度问题
- 生成进度报告
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import glob


class JinduMonitor:
    """进度监控器"""

    # 健康度阈值（秒）
    WARNING_THRESHOLD = 30
    CRITICAL_THRESHOLD = 60
    STUCK_THRESHOLD = 120

    def __init__(self, workspace: str = "workspace"):
        self.workspace = Path(workspace)
        self.status_dir = self.workspace / "status"

    def get_overall_progress(self) -> Dict:
        """
        获取整体进度

        Returns:
            进度信息字典
        """
        zouzhang = self._read_zouzhang()
        if not zouzhang:
            return {"error": "未找到奏折"}

        subtasks = zouzhang.get("subtasks", [])
        total = len(subtasks)

        if total == 0:
            return {"error": "无子任务"}

        # 统计各状态数量
        completed = 0
        running = 0
        pending = 0
        failed = 0

        running_progress = 0.0

        for subtask in subtasks:
            status = subtask.get("status", "pending")
            if status == "completed":
                completed += 1
            elif status == "running":
                running += 1
                # 尝试获取运行中任务的进度
                agent_status = self._get_agent_status_for_task(subtask["id"])
                if agent_status and "progress" in agent_status:
                    running_progress += agent_status["progress"] / 100
            elif status == "failed":
                failed += 1
            else:
                pending += 1

        # 计算总进度百分比
        percentage = (completed + running_progress) / total * 100

        return {
            "task_id": zouzhang.get("task_id"),
            "task_name": zouzhang.get("task_name"),
            "total": total,
            "completed": completed,
            "running": running,
            "pending": pending,
            "failed": failed,
            "percentage": round(percentage, 1),
            "eta_seconds": self._estimate_eta(zouzhang, completed, running_progress, total)
        }

    def get_agent_health(self) -> Dict[str, Dict]:
        """
        获取所有Agent的健康状态

        Returns:
            {agent_id: health_info}
        """
        health_status = {}

        for status_file in self.status_dir.glob("*.json"):
            if status_file.name == "main.json":
                continue

            try:
                with open(status_file, 'r', encoding='utf-8') as f:
                    agent_status = json.load(f)

                agent_id = agent_status.get("agent_id", status_file.stem)
                health = self._check_health(agent_status)
                health_status[agent_id] = {
                    "status": agent_status.get("status", "unknown"),
                    "health": health["level"],
                    "issues": health["issues"],
                    "last_activity": agent_status.get("last_activity"),
                    "idle_seconds": self._calc_idle_seconds(agent_status)
                }
            except Exception as e:
                health_status[status_file.stem] = {
                    "status": "error",
                    "health": "critical",
                    "issues": [f"读取状态失败: {e}"]
                }

        return health_status

    def get_queue_status(self) -> Dict:
        """
        获取排队状态

        Returns:
            排队信息
        """
        queued_agents = []
        for status_file in self.status_dir.glob("*.json"):
            if status_file.name == "main.json":
                continue

            try:
                with open(status_file, 'r', encoding='utf-8') as f:
                    agent_status = json.load(f)

                if agent_status.get("status") == "queued":
                    queued_agents.append({
                        "agent_id": agent_status.get("agent_id"),
                        "dept": agent_status.get("dept"),
                        "waiting_for": agent_status.get("waiting_for"),
                        "queued_at": agent_status.get("queued_at"),
                        "queue_seconds": self._calc_queue_seconds(agent_status)
                    })
            except:
                pass

        return {
            "total_queued": len(queued_agents),
            "agents": queued_agents
        }

    def generate_report(self) -> str:
        """
        生成进度报告（Markdown格式）

        Returns:
            Markdown格式的报告
        """
        progress = self.get_overall_progress()
        health = self.get_agent_health()
        queue = self.get_queue_status()

        lines = [
            "## 【进度奏章】",
            "",
            f"### 整体进度: {progress.get('percentage', 0)}%",
            "",
            self._progress_bar(progress.get('percentage', 0)),
            "",
            f"- 已完成: {progress.get('completed', 0)}/{progress.get('total', 0)} 子任务",
            f"- 正在执行: {progress.get('running', 0)} 个Agent",
            f"- 排队等待: {queue.get('total_queued', 0)} 个Agent",
        ]

        if progress.get('eta_seconds'):
            lines.append(f"- 预计剩余: 约 {self._format_duration(progress['eta_seconds'])}")

        lines.append("")
        lines.append("### Agent状态")
        lines.append("")
        lines.append("| Agent | 部门 | 状态 | 健康度 |")
        lines.append("|-------|------|------|--------|")

        # 按部门排序
        for agent_id, info in sorted(health.items()):
            status_icon = self._status_icon(info.get("status", "unknown"))
            health_icon = self._health_icon(info.get("health", "unknown"))
            dept = info.get("dept", "未知")
            lines.append(f"| {agent_id} | {dept} | {status_icon} | {health_icon} |")

        # 健康度汇总
        health_summary = {"healthy": 0, "warning": 0, "critical": 0, "stuck": 0}
        for info in health.values():
            level = info.get("health", "healthy")
            if level in health_summary:
                health_summary[level] += 1

        lines.append("")
        lines.append("### 健康度汇总")
        lines.append("")
        lines.append(f"- ✅ 健康: {health_summary['healthy']} 个")
        lines.append(f"- ⚠️ 警告: {health_summary['warning']} 个")
        lines.append(f"- 🔴 危险: {health_summary['critical']} 个")
        lines.append(f"- 💀 卡住: {health_summary['stuck']} 个")

        return "\n".join(lines)

    def _read_zouzhang(self) -> Optional[Dict]:
        """读取奏折"""
        zouzhang_path = self.workspace / "zouzhang.json"
        if not zouzhang_path.exists():
            return None
        with open(zouzhang_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _get_agent_status_for_task(self, task_id: str) -> Optional[Dict]:
        """获取执行指定任务的Agent状态"""
        for status_file in self.status_dir.glob("*.json"):
            if status_file.name == "main.json":
                continue
            try:
                with open(status_file, 'r', encoding='utf-8') as f:
                    agent_status = json.load(f)
                if agent_status.get("task_id") == task_id:
                    return agent_status
            except:
                pass
        return None

    def _check_health(self, agent_status: Dict) -> Dict:
        """检查单个Agent的健康度"""
        issues = []
        level = "healthy"

        idle_seconds = self._calc_idle_seconds(agent_status)

        if idle_seconds > self.STUCK_THRESHOLD:
            level = "stuck"
            issues.append(f"无响应 {idle_seconds}秒")
        elif idle_seconds > self.CRITICAL_THRESHOLD:
            level = "critical"
            issues.append(f"响应慢 {idle_seconds}秒")
        elif idle_seconds > self.WARNING_THRESHOLD:
            level = "warning"
            issues.append(f"响应延迟 {idle_seconds}秒")

        # 检查错误
        if agent_status.get("error_count", 0) > 2:
            if level == "healthy":
                level = "warning"
            issues.append("多次错误")

        return {"level": level, "issues": issues}

    def _calc_idle_seconds(self, agent_status: Dict) -> int:
        """计算空闲秒数"""
        last_activity = agent_status.get("last_activity")
        if not last_activity:
            return 0

        try:
            last_time = datetime.fromisoformat(last_activity)
            now = datetime.now()
            return int((now - last_time).total_seconds())
        except:
            return 0

    def _calc_queue_seconds(self, agent_status: Dict) -> int:
        """计算排队秒数"""
        queued_at = agent_status.get("queued_at")
        if not queued_at:
            return 0

        try:
            queued_time = datetime.fromisoformat(queued_at)
            now = datetime.now()
            return int((now - queued_time).total_seconds())
        except:
            return 0

    def _estimate_eta(self, zouzhang: Dict, completed: int, running_progress: float, total: int) -> Optional[int]:
        """预估剩余时间（秒）"""
        if completed == 0:
            return None

        # 简单预估：假设每个子任务平均耗时相同
        # 实际应该基于历史数据
        remaining = total - completed - running_progress
        # 假设每个子任务平均3分钟
        avg_time = 180
        return int(remaining * avg_time)

    def _progress_bar(self, percentage: float, width: int = 20) -> str:
        """生成进度条"""
        filled = int(percentage / 100 * width)
        empty = width - filled
        return f"[{'█' * filled}{'░' * empty}] {percentage}%"

    def _status_icon(self, status: str) -> str:
        """状态图标"""
        icons = {
            "running": "🔄运行",
            "completed": "✅完成",
            "queued": "⏳排队",
            "failed": "❌失败",
            "idle": "💤空闲"
        }
        return icons.get(status, f"❓{status}")

    def _health_icon(self, health: str) -> str:
        """健康度图标"""
        icons = {
            "healthy": "✅健康",
            "warning": "⚠️警告",
            "critical": "🔴危险",
            "stuck": "💀卡住"
        }
        return icons.get(health, f"❓{health}")

    def _format_duration(self, seconds: int) -> str:
        """格式化时长"""
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            return f"{seconds // 60}分钟"
        else:
            return f"{seconds // 3600}小时{(seconds % 3600) // 60}分钟"


if __name__ == "__main__":
    # 测试
    monitor = JinduMonitor()

    print("进度报告:")
    print(monitor.generate_report())