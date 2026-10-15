"""
template_manager.py — Nạp và "điền chỗ trống" cho các file prompt .jinja.

Tại sao tách prompt ra file .jinja riêng thay vì viết thẳng trong code?
  - Dễ đọc, dễ sửa lời nhắc mà không đụng vào logic Python.
  - Tách "câu chữ nói với AI" khỏi "code xử lý" — một thói quen tốt.

Jinja là thư viện template: trong file .jinja có chỗ {{ text_content }},
khi render ta truyền text_content vào, nó thay vào đúng chỗ đó.
"""

import os
from jinja2 import Environment, FileSystemLoader

import config


class TemplateManager:
    def __init__(self, template_dir: str = None):
        template_dir = template_dir or config.PROMPTS_DIR
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, name: str, **variables) -> str:
        """
        Nạp file `<name>.jinja` và điền các biến vào.
        Ví dụ: render("basics", text_content=cv_text)
        """
        template = self.env.get_template(f"{name}.jinja")
        return template.render(**variables)
