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

from services.hwpx_service import (  # noqa: E402
    read_hwpx, split_problems, filter_hwpx_by_numbers,
    merge_reference_problem, append_hwpx_problems,
)

sys.path.insert(0, str(PROJECT_ROOT))
from tools.similarity_finder import comparator, converter, multi_file_input  # noqa: E402
from tools.similarity_finder.multi_file_input import PreparedEntry  # noqa: E402


class SimilarityFinderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("유사문제 찾기")
        self.root.geometry("700x600")

        self.original_path = tk.StringVar()
        self.problems_path = tk.StringVar()  # 요약 표시용 ("3개 파일 선택됨" 등)
        self.model_var = tk.StringVar(value="claude-sonnet-4-6")
        self.export_mode_var = tk.StringVar(value="copy")  # "copy" | "cut"
        self.last_result: dict | None = None
        self.is_searching = False

        # 복수 문제집 파일 큐 (multi_file_input.PreparedEntry 리스트)
        self.problems_entries: list[PreparedEntry] = []
        # 원본이 HWP였을 때 변환된 임시 entry (정리용)
        self._original_entry: PreparedEntry | None = None

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
        # 변환된 임시 HWPX 정리 + 한컴 COM 인스턴스 종료
        try:
            multi_file_input.cleanup(self.problems_entries)
            if self._original_entry is not None:
                multi_file_input.cleanup([self._original_entry])
        except Exception:
            pass
        try:
            converter.shutdown()
        except Exception:
            pass
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

        # HWPX 추출 UI (복사/잘라내기 + 내보내기 버튼)
        export_frame = ttk.LabelFrame(frm, text="HWPX 추출", padding=5)
        export_frame.grid(row=11, column=0, columnspan=2, sticky="we", pady=(5, 0))
        ttk.Radiobutton(export_frame, text="복사 (원본 유지)", variable=self.export_mode_var,
                        value="copy").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(export_frame, text="잘라내기 (원본에서 제거)", variable=self.export_mode_var,
                        value="cut").pack(side=tk.LEFT, padx=(0, 10))
        self.export_btn = ttk.Button(export_frame, text="HWPX로 내보내기",
                                     command=self._on_export, state=tk.DISABLED)
        self.export_btn.pack(side=tk.LEFT, padx=(10, 0))

        # grid 확장 설정
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(9, weight=1)

    def _pick_original(self):
        path = filedialog.askopenfilename(
            title="원본 문제 HWPX/HWP 선택",
            filetypes=[("한글 문서", "*.hwp *.hwpx"),
                       ("HWPX 파일", "*.hwpx"),
                       ("HWP 파일", "*.hwp"),
                       ("모든 파일", "*.*")],
        )
        if not path:
            return

        # 이전에 변환했던 원본 임시 파일이 있다면 정리
        if self._original_entry is not None:
            try:
                multi_file_input.cleanup([self._original_entry])
            except Exception:
                pass
            self._original_entry = None

        p = Path(path)
        if p.suffix.lower() == ".hwp":
            # HWP는 즉석 변환
            self._update_status(f"원본 HWP 변환 중: {p.name}")
            result = converter.hwp_to_tempfile(p)
            if not result.ok or result.hwpx_path is None:
                messagebox.showerror("HWP 변환 실패", result.message)
                self._update_status("대기 중")
                return
            self._original_entry = PreparedEntry(
                source_path=p, hwpx_path=result.hwpx_path, converted=True
            )
            self.original_path.set(str(result.hwpx_path))
            self._update_status(f"원본 변환 완료: {p.name}")
        else:
            self.original_path.set(str(p))

    def _pick_problems(self):
        # 복수 파일 선택 + HWP 자동 변환
        def _progress(idx, total, msg):
            self._update_status(msg)

        # 이전 큐 정리
        if self.problems_entries:
            try:
                multi_file_input.cleanup(self.problems_entries)
            except Exception:
                pass
            self.problems_entries = []

        queue, errors = multi_file_input.select_files_and_prepare(
            parent=self.root, progress_cb=_progress
        )

        if errors:
            err_lines = [f"• {e.source_path.name}: {e.message}" for e in errors]
            messagebox.showwarning(
                "일부 파일 스킵됨",
                "다음 파일은 처리에서 제외되었습니다:\n\n" + "\n".join(err_lines),
            )

        if not queue:
            if not errors:
                self._update_status("대기 중")
            return

        self.problems_entries = queue
        if len(queue) == 1:
            self.problems_path.set(str(queue[0].hwpx_path))
        else:
            names = ", ".join(e.source_path.name for e in queue[:3])
            suffix = f" 외 {len(queue) - 3}개" if len(queue) > 3 else ""
            self.problems_path.set(f"{len(queue)}개 파일: {names}{suffix}")
        self._update_status(f"문제집 {len(queue)}개 준비 완료")

    def _on_search(self):
        if self.is_searching:
            return

        original_path = self.original_path.get().strip()

        if not original_path:
            messagebox.showwarning("입력 부족", "원본 파일을 선택해주세요.")
            return
        if not self.problems_entries:
            messagebox.showwarning("입력 부족", "문제집 파일을 선택해주세요.")
            return

        self._set_searching(True)
        self._clear_result()
        threading.Thread(
            target=self._run_search,
            args=(original_path, list(self.problems_entries), self.model_var.get()),
            daemon=True,
        ).start()

    def _set_searching(self, flag: bool):
        self.is_searching = flag
        if flag:
            self.search_btn.config(state=tk.DISABLED)
            self.copy_btn.config(state=tk.DISABLED)
            self.opus_btn.config(state=tk.DISABLED)
            self.export_btn.config(state=tk.DISABLED)
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

    def _run_search(self, original_path: str, entries: list, model: str):
        try:
            self._update_status("원본 파싱 중…")
            original_bytes = Path(original_path).read_bytes()
            original_text = read_hwpx(original_bytes)

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

            per_file = []  # [{"entry", "stem", "problems_count", "result"}]
            usage_sum = {"input_tokens": 0, "output_tokens": 0,
                         "cache_write": 0, "cache_read": 0}
            cost_sum_usd = 0.0

            for f_idx, entry in enumerate(entries, 1):
                p_path = Path(str(entry.hwpx_path))
                stem = entry.source_path.stem
                prefix = f"[{f_idx}/{len(entries)}] {stem}"
                self._update_status(f"{prefix}: 파싱 중…")

                try:
                    p_bytes = p_path.read_bytes()
                    p_text = read_hwpx(p_bytes)
                    problems = split_problems(p_text)
                except Exception as exc:
                    self._log_error(f"{stem} 파싱 실패: {exc}\n{traceback.format_exc()}")
                    per_file.append({"entry": entry, "stem": stem, "problems_count": 0,
                                     "result": {"쌍둥이": [], "유형유사": [],
                                                "_error": f"파싱 실패: {exc}"}})
                    continue

                if not problems or (len(problems) == 1 and problems[0]["number"] == 1
                                    and "-1번-" not in p_text):
                    per_file.append({"entry": entry, "stem": stem, "problems_count": 0,
                                     "result": {"쌍둥이": [], "유형유사": [],
                                                "_error": "'-N번-' 구분자 없음"}})
                    continue

                self._update_status(f"{prefix}: {len(problems)}문제 비교…")
                try:
                    result = comparator.compare(
                        original=original_text, problems=problems, model=model,
                        progress_callback=lambda msg, pre=prefix: self._update_status(f"{pre}: {msg}"),
                    )
                except Exception as exc:
                    self._log_error(f"{stem} 비교 실패: {exc}\n{traceback.format_exc()}")
                    per_file.append({"entry": entry, "stem": stem,
                                     "problems_count": len(problems),
                                     "result": {"쌍둥이": [], "유형유사": [],
                                                "_error": f"API 호출 실패: {exc}"}})
                    continue

                meta = result.pop("_meta", {})
                u = meta.get("usage", {})
                for k in usage_sum:
                    usage_sum[k] += u.get(k, 0)
                cost_sum_usd += meta.get("cost", {}).get("usd", 0.0)

                self._log_request(original_text, problems, model,
                                  {**result, "_source_file": stem})
                per_file.append({"entry": entry, "stem": stem,
                                 "problems_count": len(problems), "result": result})

            aggregate = {
                "per_file": per_file,
                "meta": {
                    "model": model,
                    "usage": usage_sum,
                    "cost": {"usd": cost_sum_usd,
                             "krw": int(round(cost_sum_usd * comparator._USD_TO_KRW))},
                    "file_count": len(entries),
                },
            }
            self.last_result = aggregate
            self.root.after(0, lambda: self._render_result(aggregate))

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

    def _render_result(self, aggregate: dict):
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)

        per_file = aggregate.get("per_file", [])
        total_twins = 0
        total_problems = 0

        for f_idx, fr in enumerate(per_file, 1):
            stem = fr["stem"]
            res = fr["result"]
            err = res.get("_error")
            twins = res.get("쌍둥이", [])
            total_twins += len(twins)
            total_problems += fr.get("problems_count", 0)

            header = f"📄 [{f_idx}/{len(per_file)}] {stem}"
            self.result_text.insert(tk.END, f"{header}\n", "file_head")

            if err:
                self.result_text.insert(tk.END, f"   ⚠️ {err}\n\n", "meta")
                continue

            if not twins:
                self.result_text.insert(tk.END, "   숫자 변형 문항 없음\n\n", "meta")
                continue

            self.result_text.insert(tk.END, f"   🎯 {len(twins)}개:\n", "heading")
            for item in twins:
                self.result_text.insert(
                    tk.END,
                    f"      • {item.get('번호')}번 — {item.get('이유', '')}\n",
                )
            self.result_text.insert(tk.END, "\n")

        meta = aggregate.get("meta", {})
        u = meta.get("usage", {})
        c = meta.get("cost", {})
        total_in = u.get("input_tokens", 0) + u.get("cache_write", 0) + u.get("cache_read", 0)
        self.result_text.insert(tk.END, "────────────────────\n")
        self.result_text.insert(
            tk.END,
            f"합계: {meta.get('file_count', 0)}개 파일 / {total_problems}문제 비교 / "
            f"{total_twins}개 유사문항 발견\n",
            "heading",
        )
        self.result_text.insert(tk.END, f"모델: {meta.get('model')}\n", "meta")
        self.result_text.insert(
            tk.END,
            f"입력 {total_in:,} / 출력 {u.get('output_tokens', 0):,} 토큰"
            f"  (캐시 쓰기 {u.get('cache_write', 0):,}, 읽기 {u.get('cache_read', 0):,})\n",
            "meta",
        )
        self.result_text.insert(
            tk.END,
            f"예상 비용: 약 {c.get('krw', 0):,}원 (USD ${c.get('usd', 0):.4f})\n",
            "meta",
        )

        self.result_text.tag_config("heading", font=("Malgun Gothic", 11, "bold"))
        self.result_text.tag_config("file_head",
                                    font=("Malgun Gothic", 11, "bold"),
                                    foreground="#1f4e79")
        self.result_text.tag_config("meta", foreground="#666666")
        self.result_text.config(state=tk.DISABLED)

        self.copy_btn.config(state=tk.NORMAL)
        self.opus_btn.config(state=tk.NORMAL if self.model_var.get() == "claude-sonnet-4-6" else tk.DISABLED)
        has_any = any(self._selected_numbers_by_file().values())
        self.export_btn.config(state=tk.NORMAL if has_any else tk.DISABLED)
        self._update_status(
            f"완료 — {meta.get('file_count', 0)}개 파일, {total_twins}개 유사문항"
        )

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

    def _selected_numbers_by_file(self) -> dict:
        """각 파일별 선택 번호 집합. {stem: set[int]} 형태."""
        out: dict = {}
        if not self.last_result:
            return out
        per_file = self.last_result.get("per_file", [])
        for fr in per_file:
            nums: set[int] = set()
            res = fr.get("result", {})
            for key in ("쌍둥이", "유형유사"):
                for item in res.get(key, []) or []:
                    n = item.get("번호")
                    try:
                        nums.add(int(n))
                    except (TypeError, ValueError):
                        continue
            out[fr["stem"]] = nums
        return out

    def _on_export(self):
        """HWPX 내보내기: 여러 문제집의 유사문항을 한 파일에 합치고, 기준문항을 1번으로 prepend.
        cut 모드에서는 각 문제집의 잘라내기 원본을 원본 옆에 자동 저장.
        """
        if self.is_searching:
            return

        selections = self._selected_numbers_by_file()  # {stem: set[int]}
        if not any(selections.values()):
            messagebox.showwarning("선택된 문제 없음",
                                   "결과에 유사문제 번호가 없어 내보낼 수 없습니다.")
            return
        if not self.problems_entries:
            messagebox.showwarning("문제집 없음", "문제집 파일이 선택되지 않았습니다.")
            return

        mode = self.export_mode_var.get()

        # 각 파일별로 [filter된 바이트, 선택/누락/잘라내기 메타] 준비
        per_file_prepared = []  # [(entry, chosen_nums, missing, keep_remainder_bytes, similar_bytes)]
        combined_summary = []  # 메시지용

        for entry in self.problems_entries:
            stem = entry.source_path.stem
            chosen = selections.get(stem, set())
            if not chosen:
                continue  # 이 파일에선 유사문항 0개
            p_path = Path(str(entry.hwpx_path))
            try:
                src_bytes = p_path.read_bytes()
                text = read_hwpx(src_bytes)
                all_nums = {p["number"] for p in split_problems(text)}
            except Exception as exc:
                messagebox.showerror("문제집 읽기 실패",
                                     f"{stem}: {type(exc).__name__}: {exc}")
                return

            missing = chosen - all_nums
            effective = chosen & all_nums
            if missing:
                # 조용히 제외 (파일별 누락 메시지는 합쳐서 마지막에 표시)
                combined_summary.append(f"⚠️ {stem}: 누락 번호 {sorted(missing)} 제외")
            if not effective:
                continue

            try:
                similar_bytes = filter_hwpx_by_numbers(src_bytes, effective)
            except Exception as exc:
                messagebox.showerror("추출 실패",
                                     f"{stem} 유사문항 추출 실패: {exc}")
                return

            remainder_bytes = None
            if mode == "cut":
                try:
                    remainder_bytes = filter_hwpx_by_numbers(src_bytes, all_nums - effective)
                except Exception as exc:
                    messagebox.showerror("추출 실패",
                                         f"{stem} 잘라내기 원본 생성 실패: {exc}")
                    return

            per_file_prepared.append((entry, effective, similar_bytes, remainder_bytes))
            combined_summary.append(f"✓ {stem}: {sorted(effective)}")

        if not per_file_prepared:
            messagebox.showerror("내보낼 번호 없음", "유효한 번호가 없습니다.")
            return

        # 여러 파일의 유사문항을 하나로 합침 (append_hwpx_problems 사용)
        merged_similar = per_file_prepared[0][2]
        for (_, _, sim_bytes, _) in per_file_prepared[1:]:
            try:
                merged_similar = append_hwpx_problems(merged_similar, sim_bytes)
            except Exception as exc:
                messagebox.showerror("파일 병합 실패",
                                     f"유사문항 파일 병합 중 오류: {exc}")
                return

        # 기준문항을 1번으로 prepend
        original_path = self.original_path.get().strip()
        if original_path and Path(original_path).exists():
            try:
                original_bytes = Path(original_path).read_bytes()
                merged_similar = merge_reference_problem(merged_similar, original_bytes)
            except Exception as exc:
                messagebox.showwarning(
                    "기준문항 합치기 실패",
                    f"유사문항 파일은 생성했으나 기준문항 합치기 중 오류:\n"
                    f"{type(exc).__name__}: {exc}\n\n"
                    f"기준문항 없이 유사문항만 저장합니다.",
                )

        # 저장 경로: 첫 파일 stem 기준 초기 파일명
        first_stem = per_file_prepared[0][0].source_path.stem
        default_name = (f"{first_stem}_유사문항_모음.hwpx"
                        if len(per_file_prepared) > 1
                        else f"{first_stem}_유사문항.hwpx")

        similar_save = filedialog.asksaveasfilename(
            title="유사문항 모음 파일 저장 위치",
            defaultextension=".hwpx",
            initialfile=default_name,
            filetypes=[("HWPX 파일", "*.hwpx")],
        )
        if not similar_save:
            self._update_status("내보내기 취소됨")
            return

        try:
            Path(similar_save).write_bytes(merged_similar)
        except Exception as exc:
            messagebox.showerror("저장 실패", f"{type(exc).__name__}: {exc}")
            return

        # cut 모드: 각 문제집의 잘라내기 원본을 문제집 파일 옆에 자동 저장
        saved_remainders = []
        if mode == "cut":
            for (entry, _, _, rem_bytes) in per_file_prepared:
                if rem_bytes is None:
                    continue
                src_path = entry.source_path  # 원본 업로드 파일 (hwp/hwpx)
                stem = src_path.stem
                out_path = src_path.parent / f"{stem}_잘라내기.hwpx"
                # 덮어쓰기 확인
                if out_path.exists():
                    overwrite = messagebox.askokcancel(
                        "덮어쓰기 확인",
                        f"이미 존재합니다. 덮어쓸까요?\n{out_path}",
                    )
                    if not overwrite:
                        continue
                try:
                    out_path.write_bytes(rem_bytes)
                    saved_remainders.append(str(out_path))
                except Exception as exc:
                    messagebox.showwarning(
                        "잘라내기 저장 실패",
                        f"{stem}: {type(exc).__name__}: {exc}",
                    )

        info_lines = [f"📁 유사문항 모음: {similar_save}", ""]
        info_lines += combined_summary
        if saved_remainders:
            info_lines += ["", "📎 잘라내기 원본 저장:"] + [f"  • {p}" for p in saved_remainders]

        messagebox.showinfo(
            "내보내기 완료" + (" (잘라내기)" if mode == "cut" else " (복사)"),
            "\n".join(info_lines),
        )
        self._update_status("내보내기 완료")


def main():
    root = tk.Tk()
    app = SimilarityFinderApp(root)
    if root.winfo_exists():
        root.mainloop()


if __name__ == "__main__":
    main()
