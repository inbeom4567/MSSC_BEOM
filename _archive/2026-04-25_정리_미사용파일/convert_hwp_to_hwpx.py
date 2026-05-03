"""HWP → HWPX 일괄 변환 스크립트 (한글 COM 자동화)"""
import win32com.client
import os
import glob
import time

BOOK_DIR = os.path.join(os.path.dirname(__file__), "book")

def find_hwp_files():
    pattern = os.path.join(BOOK_DIR, "**", "*.hwp")
    files = glob.glob(pattern, recursive=True)
    # .hwpx 이미 있는 것 제외
    hwpx_set = set(glob.glob(os.path.join(BOOK_DIR, "**", "*.hwpx"), recursive=True))
    result = []
    for f in files:
        hwpx_path = f + "x"
        if hwpx_path not in hwpx_set:
            result.append(f)
    return sorted(result)

def convert(hwp, src_path):
    dst_path = src_path + "x"
    try:
        hwp.Open(src_path, "HWP", "forceopen:true")
        time.sleep(0.3)
        pset = hwp.HParameterSet.HFileOpenSave
        pset.filename = dst_path
        pset.Format = "HWPX"
        pset.attributes = 0
        hwp.HAction.Execute("FileSaveAs_S", pset.HSet)
        hwp.Clear(1)
        return True, dst_path
    except Exception as e:
        return False, str(e)

def main():
    files = find_hwp_files()
    print(f"변환 대상: {len(files)}개 파일\n")

    hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
    hwp.XHwpWindows.Item(0).Visible = False  # 창 숨기기

    ok, fail = 0, 0
    for i, src in enumerate(files, 1):
        rel = os.path.relpath(src, BOOK_DIR)
        print(f"[{i}/{len(files)}] {rel} ...", end=" ", flush=True)
        success, result = convert(hwp, src)
        if success:
            print("완료")
            ok += 1
        else:
            print(f"실패: {result}")
            fail += 1

    hwp.Quit()
    print(f"\n완료 {ok}개 / 실패 {fail}개")

if __name__ == "__main__":
    main()
