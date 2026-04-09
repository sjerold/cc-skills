#!/usr/bin/env python3
"""
大唐三公六部 - 讨论流程执行器
按照配置文件执行固定的讨论流程
"""

import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


class DiscussionFlowExecutor:
    """讨论流程执行器"""

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.state: Dict[str, Any] = {}
        self.speeches: List[Dict] = []
        self.workspace = Path("workspace/meeting-minutes")
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> Dict:
        """加载流程配置"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def start_discussion(self, topic: str) -> Dict:
        """启动讨论，返回初始状态"""
        self.state = {
            "topic": topic,
            "current_phase": 0,
            "current_speaker": 0,
            "completed_phases": [],
            "start_time": datetime.now().isoformat(),
            "status": "in_progress"
        }
        self._save_state()
        return self.state

    def get_current_task(self) -> Optional[Dict]:
        """获取当前需要执行的任务"""
        phases = self.config['phases']

        if self.state["current_phase"] >= len(phases):
            return None  # 所有阶段完成

        current_phase = phases[self.state["current_phase"]]

        # 检查是否是发言阶段（有多个speaker）
        if 'speakers' in current_phase:
            speakers = current_phase['speakers']
            if self.state["current_speaker"] >= len(speakers):
                # 当前phase的所有speaker完成，进入下一phase
                self.state["current_phase"] += 1
                self.state["current_speaker"] = 0
                return self.get_current_task()

            speaker = speakers[self.state["current_speaker"]]
            return {
                "type": "speaker",
                "phase_id": current_phase['id'],
                "phase_name": current_phase['name'],
                "speaker": speaker,
                "context": self._build_context()
            }
        else:
            # 单一agent阶段
            return {
                "type": "phase",
                "phase": current_phase,
                "context": self._build_context()
            }

    def _build_context(self) -> Dict:
        """构建上下文（之前的发言内容）"""
        return {
            "topic": self.state["topic"],
            "speeches": self.speeches,
            "subtopics": self._extract_subtopics()
        }

    def _extract_subtopics(self) -> List[str]:
        """从议程中提取子议题"""
        # 简化实现，实际可解析agenda.md
        return []

    def submit_speech(self, agent_id: str, role: str, content: str):
        """提交发言内容"""
        speech = {
            "agent_id": agent_id,
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        self.speeches.append(speech)

        # 更新状态
        phases = self.config['phases']
        current_phase = phases[self.state["current_phase"]]

        if 'speakers' in current_phase:
            self.state["current_speaker"] += 1
        else:
            self.state["current_phase"] += 1

        self._save_state()

        # 保存发言记录
        self._append_speakers_log(speech)

    def _save_state(self):
        """保存状态"""
        state_file = self.workspace / "state.json"
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def _append_speakers_log(self, speech: Dict):
        """追加发言记录"""
        log_file = self.workspace / "speakers-log.md"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n## 【{speech['role']}】\n")
            f.write(f"**时间**: {speech['timestamp']}\n\n")
            f.write(speech['content'])
            f.write("\n---\n")

    def is_complete(self) -> bool:
        """检查讨论是否完成"""
        return self.state["current_phase"] >= len(self.config['phases'])

    def get_summary(self) -> Dict:
        """获取讨论摘要"""
        return {
            "topic": self.state["topic"],
            "total_phases": len(self.config['phases']),
            "completed_phases": len(self.state["completed_phases"]),
            "total_speeches": len(self.speeches),
            "status": "completed" if self.is_complete() else "in_progress"
        }


# CLI接口
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="讨论流程执行器")
    parser.add_argument("topic", help="讨论议题")
    parser.add_argument("--config", default="workflows/discussion-flow.yaml", help="流程配置文件")

    args = parser.parse_args()

    executor = DiscussionFlowExecutor(args.config)
    state = executor.start_discussion(args.topic)

    print(f"讨论启动: {args.topic}")
    print(f"状态文件: workspace/meeting-minutes/state.json")
    print(f"\n当前任务:")
    task = executor.get_current_task()
    if task:
        print(json.dumps(task, ensure_ascii=False, indent=2))