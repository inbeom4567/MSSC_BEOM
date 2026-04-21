"""유사문제 찾기 GUI — Tkinter 기반."""
from __future__ import annotations

import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# backend/services/hwpx_service import을 위한 경로 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from services.hwpx_service import read_hwpx, split_problems  # noqa: E402

sys.path.insert(0, str(PROJECT_ROOT))
from tools.similarity_finder import comparator  # noqa: E402


class SimilarityFinderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("유사문제 찾기")
        self.root.geometry("700x600")

        self.original_path = tk.StringVar()
        self.problems_path = tk.StringVar()
        self.model_var = tk.StringVar(value="claude-sonnet-4-6")
        self.last_result: dict | None = None
        self.is_searching = False

        self._build_ui()

    def _build_ui(self):
        frm = ttk.Frame(self.root, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        # 원본 파일
        ttk.Label(frm, text="원본 문제 (1문제):").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.original_path, width=60).grid(row=1, column=0, padx=(0, 5), sticky="we")
        ttk.Button(frm, text="파일 선택", command=self._pick_original).grid(row=1, column=1)

        # 문제집 파일
        ttk.Label(frm, text="문제집 (여러 문제):").grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(frm, textvariable=self.problems_path, width=60).grid(row=3, column=0, padx=(0, 5), sticky="we")
        ttk.Button(frm, text="파일 선택", command=self._pick_problems).grid(row=3, column=1)

        # 모델 라디오
        model_frame = ttk.Frame(frm)
        model_frame.grid(row=4, column=0, columnspan=2, sticky="w", pady=10)
        ttk.Label(model_frame, text="모델:").pack(side=tk.LEFT)
        ttk.Radiobutton(model_frame, text="Sonnet (기본)", variable=self.model_var,
                        value="claude-sonnet-4-6").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(model_frame, text="Opus (정밀)", variable=self.model_var,
                        value="claude-opus-4-7").pack(side=tk.LEFT)

        # 검색 버튼
        self.search_btn = ttk.Button(frm, text="유사 문제 찾기", command=self._on_search)
        self.search_btn.grid(row=5, column=0, columnspan=2, pady=5, sticky="we")

        # 진행 상태
        self.status_var = tk.StringVar(value="대기 중")
        ttk.Label(frm, textvariable=self.status_var).grid(row=6, column=0, columnspan=2, sticky="w", pady=(5, 0))
        self.progress = ttk.Progressbar(frm, mode="indeterminate")
        self.progress.grid(row=7, column=0, columnspan=2, sticky="we", pady=(0, 10))

        # 결과 영역
        ttk.Label(frm, text="결과:").grid(row=8, column=0, sticky="w")
        self.result_text = tk.Text(frm, height=18, wrap=tk.WORD)
        self.result_text.grid(row=9, column=0, columnspan=2, sticky="nsew")
        scroll = ttk.Scrollbar(frm, command=self.result_text.yview)
        scroll.grid(row=9, column=2, sticky="ns")
        self.result_text.config(yscrollcommand=scroll.set, state=tk.DISABLED)

        # 하단 버튼
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=10, column=0, columnspan=2, sticky="we", pady=5)
        self.copy_btn = ttk.Button(btn_frame, text="결과 복사", command=self._copy_result, state=tk.DISABLED)
        self.copy_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.opus_btn = ttk.Button(btn_frame, text="Opus로 재확인", command=self._retry_opus, state=tk.DISABLED)
        self.opus_btn.pack(side=tk.LEFT)

        # grid 확장 설정
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(9, weight=1)

    def _pick_original(self):
        path = filedialog.askopenfilename(
            title="원본 문제 HWPX 선택",
            filetypes=[("HWPX 파일", "*.hwpx"), ("HWP 파일", "*.hwp"), ("모든 파일", "*.*")],
        )
        if path:
            self.original_path.set(path)

    def _pick_problems(self):
        path = filedialog.askopenfilename(
            title="문제집 HWPX 선택",
            filetypes=[("HWPX 파일", "*.hwpx"), ("HWP 파일", "*.hwp"), ("모든 파일", "*.*")],
        )
        if path:
            self.problems_path.set(path)

    def _on_search(self):
        messagebox.showinfo("미구현", "검색 기능은 다음 태스크에서 구현됩니다.")

    def _copy_result(self):
        pass

    def _retry_opus(self):
        pass


def main():
    root = tk.Tk()
    SimilarityFinderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
