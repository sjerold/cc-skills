"""
奏章管理器 - 管理任务规划文件（奏折）

功能：
- 创建奏折
- 读取奏折
- 更新奏折状态
- 验证奏折格式
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


class ZouzhangManager:
    """奏章管理器"""

    def __init__(self, workspace: str = "workspace"):
        self.workspace = Path(workspace)
        self.zouzhang_path = self.workspace / "zouzhang.json"

        # 确保工作目录存在
        self.workspace.mkdir(parents=True, exist_ok=True)
        (self.workspace / "status").mkdir(exist_ok=True)
        (self.workspace / "inputs").mkdir(exist_ok=True)
        (self.workspace / "results").mkdir(exist_ok=True)
        (self.workspace / "final").mkdir(exist_ok=True)
        (self.workspace / "errors").mkdir(exist_ok=True)

    def create_zouzhang(
        self,
        task_name: str,
        level: str,
        subtasks: List[Dict],
        input_analysis: Optional[Dict] = None,
        output_requirements: Optional[Dict] = None,
        parallel_groups: Optional[List[List[str]]] = None,
        qa_mode: str = "standard"
    ) -> Dict:
        """
        创建奏折

        Args:
            task_name: 任务名称
            level: 任务等级 (simple/medium/complex)
            subtasks: 子任务列表
            input_analysis: 输入分析
            output_requirements: 输出要求
            parallel_groups: 并行分组
            qa_mode: QA模式 (strict/standard/quick)

        Returns:
            奏折数据
        """
        import uuid

        zouzhang = {
            "task_id": str(uuid.uuid4()),
            "task_name": task_name,
            "level": level,
            "input_analysis": input_analysis or {
                "types": ["text"],
                "summary": task_name
            },
            "output_requirements": output_requirements or {
                "formats": ["markdown"],
                "description": "输出结果"
            },
            "subtasks": subtasks,
            "parallel_groups": parallel_groups or [[s["id"] for s in subtasks]],
            "qa_mode": qa_mode,
            "created_at": datetime.now().isoformat(),
            "status": "pending",
            "iteration": 0
        }

        self._save(zouzhang)
        return zouzhang

    def read_zouzhang(self) -> Optional[Dict]:
        """读取奏折"""
        if not self.zouzhang_path.exists():
            return None

        with open(self.zouzhang_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def update_status(self, status: str):
        """更新奏折状态"""
        zouzhang = self.read_zouzhang()
        if zouzhang:
            zouzhang["status"] = status
            zouzhang["updated_at"] = datetime.now().isoformat()
            self._save(zouzhang)

    def increment_iteration(self):
        """增加迭代次数"""
        zouzhang = self.read_zouzhang()
        if zouzhang:
            zouzhang["iteration"] = zouzhang.get("iteration", 0) + 1
            zouzhang["updated_at"] = datetime.now().isoformat()
            self._save(zouzhang)

    def update_subtask_status(self, subtask_id: str, status: str, result_file: Optional[str] = None):
        """更新子任务状态"""
        zouzhang = self.read_zouzhang()
        if not zouzhang:
            return

        for subtask in zouzhang.get("subtasks", []):
            if subtask["id"] == subtask_id:
                subtask["status"] = status
                if result_file:
                    subtask["result_file"] = result_file
                break

        self._save(zouzhang)

    def validate_zouzhang(self, zouzhang: Dict) -> Dict[str, Any]:
        """
        验证奏折格式

        Returns:
            {"valid": bool, "errors": List[str], "warnings": List[str]}
        """
        errors = []
        warnings = []

        # 必需字段检查
        required_fields = ["task_id", "task_name", "level", "subtasks"]
        for field in required_fields:
            if field not in zouzhang:
                errors.append(f"缺少必需字段: {field}")

        # 等级检查
        if zouzhang.get("level") not in ["simple", "medium", "complex"]:
            errors.append("level 必须是 simple/medium/complex 之一")

        # 子任务检查
        if "subtasks" in zouzhang:
            subtask_ids = set()
            for i, subtask in enumerate(zouzhang["subtasks"]):
                if "id" not in subtask:
                    errors.append(f"子任务 {i} 缺少 id")
                elif subtask["id"] in subtask_ids:
                    errors.append(f"子任务 id 重复: {subtask['id']}")
                else:
                    subtask_ids.add(subtask["id"])

                if "assigned_dept" not in subtask:
                    warnings.append(f"子任务 {subtask.get('id', i)} 未指定部门")

        # 并行分组检查
        if "parallel_groups" in zouzhang:
            all_ids = set(s["id"] for s in zouzhang.get("subtasks", []))
            for group in zouzhang["parallel_groups"]:
                for task_id in group:
                    if task_id not in all_ids:
                        errors.append(f"并行分组中的任务 {task_id} 不存在于子任务列表")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def get_next_subtasks(self) -> List[Dict]:
        """获取下一批可执行的子任务（依赖已满足）"""
        zouzhang = self.read_zouzhang()
        if not zouzhang:
            return []

        completed_ids = set()
        for subtask in zouzhang.get("subtasks", []):
            if subtask.get("status") == "completed":
                completed_ids.add(subtask["id"])

        ready_tasks = []
        for subtask in zouzhang.get("subtasks", []):
            if subtask.get("status") in [None, "pending"]:
                deps = subtask.get("dependencies", [])
                if all(d in completed_ids for d in deps):
                    ready_tasks.append(subtask)

        return ready_tasks

    def _save(self, zouzhang: Dict):
        """保存奏折"""
        with open(self.zouzhang_path, 'w', encoding='utf-8') as f:
            json.dump(zouzhang, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # 测试
    manager = ZouzhangManager()

    # 创建测试奏折
    zouzhang = manager.create_zouzhang(
        task_name="分析项目架构",
        level="medium",
        subtasks=[
            {
                "id": "subtask-1",
                "description": "解析输入文件",
                "assigned_dept": "户部",
                "dependencies": []
            },
            {
                "id": "subtask-2",
                "description": "分析代码结构",
                "assigned_dept": "兵部",
                "dependencies": ["subtask-1"]
            },
            {
                "id": "subtask-3",
                "description": "生成分析报告",
                "assigned_dept": "礼部",
                "dependencies": ["subtask-2"]
            }
        ]
    )

    print("奏折创建成功:")
    print(json.dumps(zouzhang, ensure_ascii=False, indent=2))

    # 验证
    result = manager.validate_zouzhang(zouzhang)
    print(f"\n验证结果: {result}")