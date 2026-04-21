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
        self._verify_api_key()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _verify_api_key(self):
        try:
            comparator._load_api_key()
        except RuntimeError as e:
            messagebox.showerror("API 키 누락", str(e))
            self.root.destroy()

    def _on_close(self):
        if self.is_searching:
            if not messagebox.askokcancel("검색 중", "검색이 진행 중입니다. 종료하시겠습니까?"):
                return
        self.root.destroy()

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
        if self.is_searching:
            return

        original_path = self.original_path.get().strip()
        problems_path = self.problems_path.get().strip()

        if not original_path or not problems_path:
            messagebox.showwarning("입력 부족", "두 파일을 모두 선택해주세요.")
            return

        if original_path.lower().endswith(".hwp") or problems_path.lower().endswith(".hwp"):
            messagebox.showerror(
                "HWP 미지원",
                "구버전 HWP 파일은 지원하지 않습니다.\n한글에서 HWPX로 저장한 뒤 다시 시도하세요.",
            )
            return

        self._set_searching(True)
        self._clear_result()
        threading.Thread(
            target=self._run_search,
            args=(original_path, problems_path, self.model_var.get()),
            daemon=True,
        ).start()

    def _set_searching(self, flag: bool):
        self.is_searching = flag
        if flag:
            self.search_btn.config(state=tk.DISABLED)
            self.copy_btn.config(state=tk.DISABLED)
            self.opus_btn.config(state=tk.DISABLED)
            self.progress.start(10)
        else:
            self.search_btn.config(state=tk.NORMAL)
            self.progress.stop()

    def _clear_result(self):
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)
        self.result_text.config(state=tk.DISABLED)
        self.last_result = None

    def _update_status(self, msg: str):
        self.root.after(0, lambda: self.status_var.set(msg))

    def _run_search(self, original_path: str, problems_path: str, model: str):
        try:
            self._update_status("원본 파싱 중…")
            original_bytes = Path(original_path).read_bytes()
            original_text = read_hwpx(original_bytes)

            # 원본에 문제가 2개 이상이면 첫 번째만 사용 (경고)
            original_problems = split_problems(original_text)
            if len(original_problems) > 1:
                use_first = messagebox.askokcancel(
                    "다중 문제 감지",
                    f"원본 파일에 문제가 {len(original_problems)}개 감지되었습니다.\n첫 번째 문제만 사용하시겠습니까?",
                )
                if not use_first:
                    self._update_status("취소됨")
                    self._set_searching(False)
                    return
                original_text = original_problems[0]["text"]

            self._update_status("문제집 파싱 중…")
            problems_bytes = Path(problems_path).read_bytes()
            problems_text = read_hwpx(problems_bytes)
            problems = split_problems(problems_text)

            if not problems or (len(problems) == 1 and problems[0]["number"] == 1 and "-1번-" not in problems_text):
                messagebox.showerror("문제 감지 실패", "문제집에서 '-N번-' 구분자를 찾지 못했습니다.")
                self._update_status("실패")
                self._set_searching(False)
                return

            self._update_status(f"총 {len(problems)}문제 발견. Claude 호출 시작…")
            result = comparator.compare(
                original=original_text,
                problems=problems,
                model=model,
                progress_callback=self._update_status,
            )
            self._log_request(original_text, problems, model, result)
            self.last_result = result
            self.root.after(0, lambda: self._render_result(result, problems_count=len(problems)))

        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            trace = traceback.format_exc()
            self.root.after(0, lambda: messagebox.showerror("검색 실패", f"{err}\n\n자세한 내용은 로그를 확인하세요."))
            self._log_error(trace)
            self._update_status(f"오류: {err}")
        finally:
            self._set_searching(False)

    def _log_request(self, original: str, problems: list[dict], model: str, result: dict):
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        (log_dir / f"{stamp}.log").write_text(
            f"MODEL={model}\nPROBLEMS={len(problems)}\n\n=== ORIGINAL ===\n{original}\n\n=== RESULT ===\n{result}\n",
            encoding="utf-8",
        )

    def _log_error(self, trace: str):
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        (log_dir / f"error_{stamp}.log").write_text(trace, encoding="utf-8")

    def _render_result(self, result: dict, problems_count: int):
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)

        twins = result.get("쌍둥이", [])
        similar = result.get("유형유사", [])

        if not twins and not similar:
            self.result_text.insert(tk.END, "유사한 문제를 찾지 못했습니다.\n")
        else:
            self.result_text.insert(tk.END, f"🎯 쌍둥이급 (숫자만 변형) — {len(twins)}개\n", "heading")
            if twins:
                for item in twins:
                    self.result_text.insert(tk.END, f"  • {item.get('번호')}번 — {item.get('이유', '')}\n")
            else:
                self.result_text.insert(tk.END, "  (없음)\n")

            self.result_text.insert(tk.END, f"\n📚 유형 유사 — {len(similar)}개\n", "heading")
            if similar:
                for item in similar:
                    self.result_text.insert(tk.END, f"  • {item.get('번호')}번 — {item.get('이유', '')}\n")
            else:
                self.result_text.insert(tk.END, "  (없음)\n")

        self.result_text.tag_config("heading", font=("Malgun Gothic", 11, "bold"))
        self.result_text.config(state=tk.DISABLED)

        self.copy_btn.config(state=tk.NORMAL)
        self.opus_btn.config(state=tk.NORMAL if self.model_var.get() == "claude-sonnet-4-6" else tk.DISABLED)
        self._update_status(f"완료 (총 {problems_count}문제 비교)")

    def _copy_result(self):
        text = self.result_text.get("1.0", tk.END).strip()
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._update_status("결과가 클립보드에 복사됨")

    def _retry_opus(self):
        if self.is_searching:
            return
        self.model_var.set("claude-opus-4-7")
        self._on_search()


def main():
    root = tk.Tk()
    app = SimilarityFinderApp(root)
    if root.winfo_exists():
        root.mainloop()


if __name__ == "__main__":
    main()
