#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量图片生成器
支持系统提示词和需求提示词的组合生成
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from .image_generator import get_image_generator

@dataclass
class GenerationTask:
    """图片生成任务"""
    id: str
    system_prompt: str
    requirement_prompt: str
    filename: str
    folder: str = "batch_images"

    def get_full_prompt(self) -> str:
        """获取完整的提示词"""
        return f"{self.system_prompt} {self.requirement_prompt}".strip()

class BatchImageGenerator:
    """批量图片生成器"""

    def __init__(self, config_path: str = None):
        """
        初始化批量生成器

        Args:
            config_path: 批量配置文件路径
        """
        if config_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(base_dir, "..", "data", "batch_config.json")
            
        self.config_path = config_path
        self.generator = get_image_generator()
        self.system_prompts = {}
        self.requirement_prompts = []
        self.generation_history = []
        self.load_config()

    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.system_prompts = config.get('system_prompts', {})
                    self.requirement_prompts = config.get('requirement_prompts', [])
                    self.generation_history = config.get('generation_history', [])
                    print(f"配置文件已加载: {self.config_path}")
            else:
                print(f"配置文件不存在，使用默认配置: {self.config_path}")
                self.create_default_config()
        except Exception as e:
            print(f"配置文件加载失败: {e}")
            self.create_default_config()

    def create_default_config(self):
        """创建默认配置"""
        self.system_prompts = {
            "ppt_education": "为教育PPT生成图片，风格简洁现代，色彩明亮，适合教学使用",
            "tech_business": "商务科技风格图片，专业简洁，蓝色调为主，适合企业演示",
            "creative_artistic": "创意艺术风格图片，色彩丰富，具有艺术感和创意性",
            "cartoon_educational": "卡通教育风格图片，友好可爱，适合儿童教育内容",
            "minimal_diagram": "简约图表风格，线条清晰，信息突出，适合技术说明"
        }

        self.requirement_prompts = [
            "AI机器人教学场景，未来科技感",
            "数据分析图表，可视化展示",
            "运动人体骨骼追踪，蓝色光点效果",
            "特征工程流程图，数据处理过程",
            "机器学习神经网络，紫色蓝色未来感"
        ]

        self.save_config()

    def save_config(self):
        """保存配置文件"""
        try:
            config = {
                "system_prompts": self.system_prompts,
                "requirement_prompts": self.requirement_prompts,
                "generation_history": self.generation_history[-20:]  # 只保存最近20条记录
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"配置文件已保存: {self.config_path}")
        except Exception as e:
            print(f"配置文件保存失败: {e}")

    def add_system_prompt(self, key: str, prompt: str):
        """添加系统提示词"""
        self.system_prompts[key] = prompt
        self.save_config()
        print(f"系统提示词已添加: {key}")

    def add_requirement_prompt(self, prompt: str):
        """添加需求提示词"""
        self.requirement_prompts.append(prompt)
        self.save_config()
        print(f"需求提示词已添加: {prompt[:30]}...")

    def remove_system_prompt(self, key: str):
        """删除系统提示词"""
        if key in self.system_prompts:
            del self.system_prompts[key]
            self.save_config()
            print(f"系统提示词已删除: {key}")
        else:
            print(f"系统提示词不存在: {key}")

    def remove_requirement_prompt(self, index: int):
        """删除需求提示词"""
        if 0 <= index < len(self.requirement_prompts):
            removed = self.requirement_prompts.pop(index)
            self.save_config()
            print(f"需求提示词已删除: {removed[:30]}...")
        else:
            print(f"索引超出范围: {index}")

    def list_prompts(self):
        """列出所有提示词"""
        print("\n系统提示词:")
        for i, (key, prompt) in enumerate(self.system_prompts.items()):
            print(f"  {i+1}. {key}: {prompt}")

        print(f"\n需求提示词 ({len(self.requirement_prompts)}个):")
        for i, prompt in enumerate(self.requirement_prompts):
            print(f"  {i+1}. {prompt}")

    def generate_batch(
        self,
        system_key: str = None,
        requirement_indices: List[int] = None,
        custom_combinations: List[Dict] = None,
        model: str = None,
        base_url: str = None,
        api_key: str = None,
        optimize: bool = False,
        output_dir: str = None,
        max_workers: int = 1,
        delay_seconds: float = 0.0,
    ) -> Dict[str, Any]:
        """
        批量生成图片

        Args:
            system_key: 系统提示词键名，None表示使用所有系统提示词
            requirement_indices: 需求提示词索引列表，None表示使用所有需求提示词
            custom_combinations: 自定义组合列表 [{"system_key": "xxx", "requirement_index": 0}, ...]

        Returns:
            Dict: 生成结果
        """
        print("\n开始批量生成图片...")

        # 生成任务列表
        tasks = self._create_tasks(system_key, requirement_indices, custom_combinations)

        if not tasks:
            print("没有找到匹配的生成任务")
            return {"success": False, "message": "没有找到匹配的生成任务"}

        print(f"共 {len(tasks)} 个生成任务")

        # 执行批量生成
        results = {
            "success": True,
            "total_tasks": len(tasks),
            "successful": 0,
            "failed": 0,
            "files": {},
            "errors": [],
            "items": []
        }

        start_time = time.time()
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            for task in tasks:
                task.folder = output_dir

        def _run_task(task: GenerationTask, idx: int) -> Tuple[int, Dict[str, Any], Optional[Dict[str, Any]]]:
            print(f"\n任务 {idx+1}/{len(tasks)}: {task.id}")
            print(f"   系统提示: {task.system_prompt[:50]}...")
            print(f"   需求提示: {task.requirement_prompt[:50]}...")

            prompt = task.get_full_prompt()
            try:
                generator = get_image_generator()
                if optimize:
                    try:
                        optimized = generator.optimize_prompt(prompt, model=model)
                        prompt = optimized or task.get_full_prompt()
                    except Exception:
                        prompt = task.get_full_prompt()

                file_path = generator.generate_and_download(
                    prompt,
                    task.filename,
                    task.folder,
                    base_url=base_url,
                    api_key=api_key,
                    model=model
                )

                if delay_seconds > 0:
                    time.sleep(delay_seconds)

                if file_path:
                    item = {
                        "id": task.id,
                        "system_prompt": task.system_prompt,
                        "requirement_prompt": task.requirement_prompt,
                        "prompt": prompt,
                        "file_path": file_path
                    }
                    history = {
                        "id": task.id,
                        "system_prompt": task.system_prompt,
                        "requirement_prompt": task.requirement_prompt,
                        "file_path": file_path,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    print(f"   成功: {file_path}")
                    return idx, item, history

                error_msg = f"图片生成失败: {task.id}"
                print(f"   失败: {error_msg}")
                return idx, {
                    "id": task.id,
                    "system_prompt": task.system_prompt,
                    "requirement_prompt": task.requirement_prompt,
                    "prompt": prompt,
                    "file_path": None,
                    "error": error_msg
                }, None

            except Exception as e:
                error_msg = f"任务执行异常: {task.id} - {str(e)}"
                print(f"   异常: {error_msg}")
                return idx, {
                    "id": task.id,
                    "system_prompt": task.system_prompt,
                    "requirement_prompt": task.requirement_prompt,
                    "prompt": prompt,
                    "file_path": None,
                    "error": error_msg
                }, None

        items: List[Tuple[int, Dict[str, Any], Optional[Dict[str, Any]]]] = []
        history_items: List[Dict[str, Any]] = []

        workers = max(1, int(max_workers or 1))
        if workers == 1:
            for idx, task in enumerate(tasks):
                result = _run_task(task, idx)
                items.append(result)
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(_run_task, task, idx): idx for idx, task in enumerate(tasks)}
                for future in as_completed(futures):
                    items.append(future.result())

        items.sort(key=lambda x: x[0])
        for _, item, history in items:
            if item.get("file_path"):
                results["files"][item["id"]] = item["file_path"]
                results["successful"] += 1
            else:
                results["failed"] += 1
                if item.get("error"):
                    results["errors"].append(item["error"])
            results["items"].append(item)
            if history:
                history_items.append(history)

        # 记录到历史
        if history_items:
            self.generation_history.extend(history_items)
            self.save_config()

        end_time = time.time()
        duration = end_time - start_time

        print(f"\n批量生成完成！")
        print(f"   总耗时: {duration:.1f}秒")
        print(f"   成功: {results['successful']}/{results['total_tasks']}")
        print(f"   失败: {results['failed']}")

        return results

    def _create_tasks(self, system_key: str = None, requirement_indices: List[int] = None,
                     custom_combinations: List[Dict] = None) -> List[GenerationTask]:
        """创建生成任务列表"""
        tasks = []

        if custom_combinations:
            # 使用自定义组合
            for combo in custom_combinations:
                sys_key = combo.get("system_key")
                req_index = combo.get("requirement_index")

                if (sys_key in self.system_prompts and
                    0 <= req_index < len(self.requirement_prompts)):

                    task = GenerationTask(
                        id=f"{sys_key}_{req_index}",
                        system_prompt=self.system_prompts[sys_key],
                        requirement_prompt=self.requirement_prompts[req_index],
                        filename=f"{sys_key}_{req_index}.png"
                    )
                    tasks.append(task)
        else:
            # 使用系统提示词和需求提示词的组合
            if system_key:
                system_keys = [system_key] if system_key in self.system_prompts else []
            else:
                system_keys = list(self.system_prompts.keys())

            if requirement_indices:
                req_indices = [i for i in requirement_indices if 0 <= i < len(self.requirement_prompts)]
            else:
                req_indices = list(range(len(self.requirement_prompts)))

            # 生成笛卡尔积
            for sys_key in system_keys:
                for req_index in req_indices:
                    task = GenerationTask(
                        id=f"{sys_key}_{req_index}",
                        system_prompt=self.system_prompts[sys_key],
                        requirement_prompt=self.requirement_prompts[req_index],
                        filename=f"{sys_key}_{req_index}.png"
                    )
                    tasks.append(task)

        return tasks

    def show_history(self, limit: int = 10):
        """显示生成历史"""
        history = self.generation_history[-limit:]
        print(f"\n📜 最近 {len(history)} 条生成记录:")
        for i, record in enumerate(history):
            print(f"  {i+1}. {record['timestamp']} - {record['id']}")
            print(f"     系统提示: {record['system_prompt'][:40]}...")
            print(f"     需求提示: {record['requirement_prompt'][:40]}...")
            print(f"     文件路径: {record['file_path']}")
            print()

def main():
    """主函数 - 交互式命令行界面"""
    print("图片生成 批量图片生成系统")
    print("=" * 50)

    generator = BatchImageGenerator()

    while True:
        print("\n列表 请选择操作:")
        print("1. 查看所有提示词")
        print("2. 添加系统提示词")
        print("3. 添加需求提示词")
        print("4. 删除系统提示词")
        print("5. 删除需求提示词")
        print("6. 批量生成图片")
        print("7. 查看生成历史")
        print("8. 生成所有组合")
        print("9. 退出")

        choice = input("\n请输入选项 (1-9): ").strip()

        if choice == "1":
            generator.list_prompts()

        elif choice == "2":
            key = input("请输入系统提示词键名: ").strip()
            prompt = input("请输入系统提示词内容: ").strip()
            if key and prompt:
                generator.add_system_prompt(key, prompt)

        elif choice == "3":
            prompt = input("请输入需求提示词: ").strip()
            if prompt:
                generator.add_requirement_prompt(prompt)

        elif choice == "4":
            generator.list_prompts()
            key = input("请输入要删除的系统提示词键名: ").strip()
            if key:
                generator.remove_system_prompt(key)

        elif choice == "5":
            generator.list_prompts()
            try:
                index = int(input("请输入要删除的需求提示词序号: ").strip()) - 1
                generator.remove_requirement_prompt(index)
            except ValueError:
                print("错误 请输入有效的数字")

        elif choice == "6":
            generator.list_prompts()
            system_key = input("请输入系统提示词键名 (回车使用所有): ").strip() or None
            req_input = input("请输入需求提示词序号，用逗号分隔 (回车使用所有): ").strip()

            requirement_indices = None
            if req_input:
                try:
                    requirement_indices = [int(x.strip()) - 1 for x in req_input.split(",")]
                except ValueError:
                    print("错误 输入格式错误")
                    continue

            results = generator.generate_batch(system_key, requirement_indices)
            if results["success"]:
                print(f"\n成功 批量生成完成！成功生成 {results['successful']} 张图片")

        elif choice == "7":
            generator.show_history()

        elif choice == "8":
            confirm = input("确定要生成所有组合吗？这可能需要较长时间 (y/N): ").strip().lower()
            if confirm == 'y':
                results = generator.generate_batch()
                if results["success"]:
                    print(f"\n成功 全部组合生成完成！成功生成 {results['successful']} 张图片")

        elif choice == "9":
            print("👋 再见！")
            break

        else:
            print("错误 无效选项，请重新选择")

if __name__ == "__main__":
    main()
