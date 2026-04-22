"""HWP → HWPX 자동 변환 모듈.

루트 ``convert_hwp_to_hwpx.py``의 검증된 한컴 COM 로직을 모듈화한 것.
유사문제 찾기 GUI가 HWP 파일을 입력받았을 때 즉석에서 HWPX로 변환한 뒤
기존 파이프라인(read_hwpx → split_problems → compare)에 그대로 흘려보낸다.

## 선택 근거 (옵션 A: pywin32 COM)
- 한컴 엔진 그대로 사용 → 수식·도형·서식 보존 최상.
- ``convert_hwp_to_hwpx.py``에서 동일 방식 검증 완료.
- 프로젝트 전제: Windows + 한컴오피스 설치.

## 제약
- Windows 전용. macOS/Linux는 미지원 (RuntimeError 반환).
- 한컴오피스 미설치 시 pywin32 Dispatch가 실패 → 사용자 친화 메시지 반환.
- COM 오버헤드로 파일당 약 1~2초. 대량 변환은 호출 측에서 배치 큐로 관리.
"""
from __future__ import annotations

import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ConvertResult:
    """변환 결과.

    Attributes:
        ok: 성공 여부.
        hwpx_path: 변환 성공 시 생성된 HWPX 경로. 실패 시 None.
        message: 사용자에게 보여줄 메시지 (실패 시 원인 요약).
    """
    ok: bool
    hwpx_path: Path | None
    message: str


# 변환 시 사용할 공유 HWP 인스턴스 (여러 파일 연속 변환 시 COM 재초기화 비용 절감).
# TODO: 세션 종료 시 hwp.Quit() 호출 타이밍 설계 필요. 현재는 프로세스 종료에 의존.
_HWP_APP = None


def _get_hwp_app():
    """한컴 COM 객체를 지연 로딩. 실패 시 RuntimeError 발생."""
    global _HWP_APP
    if _HWP_APP is not None:
        return _HWP_APP

    if sys.platform != "win32":
        raise RuntimeError(
            "HWP 자동 변환은 Windows + 한컴오피스 환경에서만 지원됩니다."
        )

    try:
        import win32com.client  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "pywin32가 설치되어 있지 않습니다. 'pip install pywin32' 후 재시도하세요."
        ) from e

    try:
        hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
        # 창 숨김 (convert_hwp_to_hwpx.py와 동일 패턴)
        hwp.XHwpWindows.Item(0).Visible = False
        # TODO: 보안 모듈 등록 시 매크로 경고 팝업 억제
        #   hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        #   → 별도 DLL 배포가 필요한 옵션이라 기본은 비활성화.
    except Exception as e:  # pythoncom.com_error 등
        raise RuntimeError(
            "한컴오피스를 찾지 못했습니다. 한컴오피스가 설치되어 있는지 확인하세요.\n"
            f"원인: {type(e).__name__}: {e}"
        ) from e

    _HWP_APP = hwp
    return hwp


def hwp_to_hwpx(hwp_path: Path, dst_path: Path | None = None) -> ConvertResult:
    """HWP 파일을 HWPX로 변환한다.

    Args:
        hwp_path: 변환할 원본 .hwp 파일 경로.
        dst_path: 저장 경로. 생략 시 ``<hwp_path>.hwpx`` 규칙으로 저장.
                  임시 파일 용도라면 호출 측에서 ``tempfile``을 통해 경로 지정 권장.

    Returns:
        ConvertResult. ok=False일 때 message에 사용자 친화 원인 포함.
    """
    hwp_path = Path(hwp_path)
    if not hwp_path.exists():
        return ConvertResult(False, None, f"파일을 찾을 수 없습니다: {hwp_path}")
    if hwp_path.suffix.lower() != ".hwp":
        return ConvertResult(
            False, None, f"HWP 파일이 아닙니다 (확장자={hwp_path.suffix}): {hwp_path}"
        )

    target = Path(dst_path) if dst_path else hwp_path.with_suffix(".hwpx")

    try:
        hwp = _get_hwp_app()
    except RuntimeError as e:
        return ConvertResult(False, None, str(e))

    # TODO: 아래 본 변환 블록은 convert_hwp_to_hwpx.py의 convert() 함수 로직과 동일.
    # 현재는 스켈레톤 → 실제 경로 문자열을 COM이 요구하는 절대경로/백슬래시로 정규화 필요.
    try:
        # 1) HWP 열기
        hwp.Open(str(hwp_path.resolve()), "HWP", "forceopen:true")
        time.sleep(0.3)  # 대용량 파일에서 Open 이벤트 완료 대기. 경험치.

        # 2) SaveAs 파라미터 세팅
        pset = hwp.HParameterSet.HFileOpenSave
        pset.filename = str(target.resolve())
        pset.Format = "HWPX"
        pset.attributes = 0

        # 3) 저장 실행
        hwp.HAction.Execute("FileSaveAs_S", pset.HSet)
        hwp.Clear(1)  # 현재 문서 닫기 (변경사항 버림)

        if not target.exists():
            return ConvertResult(
                False, None, f"변환은 호출되었으나 결과 파일이 생성되지 않았습니다: {target}"
            )

        return ConvertResult(
            True,
            target,
            f"변환 완료: {hwp_path.name} → {target.name}",
        )
    except Exception as e:
        # pythoncom.com_error 포함. 한글 자원 잠김·손상 파일 등에서 발생.
        return ConvertResult(
            False,
            None,
            f"변환 실패 ({hwp_path.name}): {type(e).__name__}: {e}",
        )


def hwp_to_tempfile(hwp_path: Path) -> ConvertResult:
    """HWP를 OS 임시 디렉터리에 HWPX로 변환. 호출 측에서 후처리·정리 책임.

    유사문제 찾기 파이프라인처럼 "읽고 버리는" 용도에 적합.
    """
    hwp_path = Path(hwp_path)
    tmp_dir = Path(tempfile.mkdtemp(prefix="similarity_finder_hwp_"))
    target = tmp_dir / (hwp_path.stem + ".hwpx")
    return hwp_to_hwpx(hwp_path, target)


def shutdown():
    """공유 HWP 인스턴스를 정리. 프로그램 종료 시 호출 권장.

    TODO: main.py의 _on_close에서 호출해 좀비 HWP 프로세스 방지.
    """
    global _HWP_APP
    if _HWP_APP is not None:
        try:
            _HWP_APP.Quit()
        except Exception:
            pass
        _HWP_APP = None
