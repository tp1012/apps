"""
Kindle for PC スクリーンショット自動取得ツール（GUI版）

使い方:
  1. Kindle for PCで対象の本を開き、開始ページを表示しておく
  2. このスクリプトを実行する
  3. 保存先フォルダ・ページ数などを設定して「開始」ボタンを押す
  4. カウントダウン後に自動キャプチャが始まる

必要ライブラリ:
  pip install pyautogui pygetwindow Pillow
"""

import os
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
from pathlib import Path

import pyautogui
import pygetwindow as gw
from PIL import Image


class KindleCaptureApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Kindle スクリーンショット取得ツール")
        self.root.resizable(False, False)

        # 状態管理
        self.is_running = False
        self.is_paused = False
        self.capture_thread = None
        self.captured_count = 0

        self._build_ui()
        self._refresh_kindle_windows()

    # ============================================================
    # UI構築
    # ============================================================
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # --- Kindleウィンドウ選択 ---
        frame_kindle = ttk.LabelFrame(self.root, text="Kindleウィンドウ", padding=8)
        frame_kindle.pack(fill="x", **pad)

        self.kindle_var = tk.StringVar()
        self.kindle_combo = ttk.Combobox(
            frame_kindle, textvariable=self.kindle_var, state="readonly", width=55
        )
        self.kindle_combo.pack(side="left", fill="x", expand=True)

        ttk.Button(frame_kindle, text="更新", width=6, command=self._refresh_kindle_windows).pack(
            side="left", padx=(8, 0)
        )

        # --- 保存設定 ---
        frame_save = ttk.LabelFrame(self.root, text="保存設定", padding=8)
        frame_save.pack(fill="x", **pad)

        # 保存先フォルダ
        row_folder = ttk.Frame(frame_save)
        row_folder.pack(fill="x", pady=2)
        ttk.Label(row_folder, text="保存先フォルダ:").pack(side="left")
        self.folder_var = tk.StringVar(value=str(Path.home() / "Desktop" / "kindle_screenshots"))
        ttk.Entry(row_folder, textvariable=self.folder_var, width=42).pack(side="left", padx=(4, 4))
        ttk.Button(row_folder, text="参照", width=5, command=self._browse_folder).pack(side="left")

        # ファイル名プレフィックス
        row_prefix = ttk.Frame(frame_save)
        row_prefix.pack(fill="x", pady=2)
        ttk.Label(row_prefix, text="ファイル名接頭辞:").pack(side="left")
        self.prefix_var = tk.StringVar(value="page")
        ttk.Entry(row_prefix, textvariable=self.prefix_var, width=16).pack(side="left", padx=(4, 0))
        ttk.Label(row_prefix, text="  (例: page_0001.jpg)").pack(side="left")

        # JPEG品質
        row_quality = ttk.Frame(frame_save)
        row_quality.pack(fill="x", pady=2)
        ttk.Label(row_quality, text="JPEG品質 (1-100):").pack(side="left")
        self.quality_var = tk.IntVar(value=85)
        ttk.Spinbox(row_quality, textvariable=self.quality_var, from_=1, to=100, width=5).pack(
            side="left", padx=(4, 0)
        )

        # --- キャプチャ設定 ---
        frame_capture = ttk.LabelFrame(self.root, text="キャプチャ設定", padding=8)
        frame_capture.pack(fill="x", **pad)

        # ページ数
        row_pages = ttk.Frame(frame_capture)
        row_pages.pack(fill="x", pady=2)
        ttk.Label(row_pages, text="ページ数:").pack(side="left")
        self.pages_var = tk.IntVar(value=10)
        ttk.Spinbox(row_pages, textvariable=self.pages_var, from_=1, to=9999, width=6).pack(
            side="left", padx=(4, 0)
        )

        # 開始番号
        row_start = ttk.Frame(frame_capture)
        row_start.pack(fill="x", pady=2)
        ttk.Label(row_start, text="開始番号:").pack(side="left")
        self.start_num_var = tk.IntVar(value=1)
        ttk.Spinbox(row_start, textvariable=self.start_num_var, from_=1, to=9999, width=6).pack(
            side="left", padx=(4, 0)
        )
        ttk.Label(row_start, text="  (途中再開時に変更)").pack(side="left")

        # カウントダウン
        row_countdown = ttk.Frame(frame_capture)
        row_countdown.pack(fill="x", pady=2)
        ttk.Label(row_countdown, text="開始カウントダウン(秒):").pack(side="left")
        self.countdown_var = tk.IntVar(value=5)
        ttk.Spinbox(row_countdown, textvariable=self.countdown_var, from_=1, to=30, width=5).pack(
            side="left", padx=(4, 0)
        )

        # ページ送り待機
        row_wait = ttk.Frame(frame_capture)
        row_wait.pack(fill="x", pady=2)
        ttk.Label(row_wait, text="ページ送り後の待機(秒):").pack(side="left")
        self.wait_var = tk.DoubleVar(value=1.5)
        ttk.Spinbox(row_wait, textvariable=self.wait_var, from_=0.5, to=10.0, increment=0.5, width=5).pack(
            side="left", padx=(4, 0)
        )

        # Kindleウィンドウ領域のみキャプチャ
        row_crop = ttk.Frame(frame_capture)
        row_crop.pack(fill="x", pady=2)
        self.crop_toolbar_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            row_crop,
            text="ウィンドウ上部のツールバー領域を除外する（上から80px）",
            variable=self.crop_toolbar_var,
        ).pack(side="left")

        # --- コントロールボタン ---
        frame_btn = ttk.Frame(self.root, padding=8)
        frame_btn.pack(fill="x")

        self.btn_start = ttk.Button(frame_btn, text="▶ 開始", command=self._on_start)
        self.btn_start.pack(side="left", padx=4)

        self.btn_pause = ttk.Button(frame_btn, text="⏸ 一時停止", command=self._on_pause, state="disabled")
        self.btn_pause.pack(side="left", padx=4)

        self.btn_stop = ttk.Button(frame_btn, text="⏹ 停止", command=self._on_stop, state="disabled")
        self.btn_stop.pack(side="left", padx=4)

        # --- 進捗 ---
        frame_progress = ttk.LabelFrame(self.root, text="進捗", padding=8)
        frame_progress.pack(fill="x", **pad)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(frame_progress, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x", pady=(0, 4))

        self.status_var = tk.StringVar(value="待機中")
        ttk.Label(frame_progress, textvariable=self.status_var).pack(anchor="w")

        # --- ログ ---
        frame_log = ttk.LabelFrame(self.root, text="ログ", padding=8)
        frame_log.pack(fill="both", expand=True, **pad)

        self.log_text = tk.Text(frame_log, height=8, width=60, state="disabled", font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(frame_log, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    # ============================================================
    # Kindleウィンドウ検出
    # ============================================================
    def _refresh_kindle_windows(self):
        windows = []
        for win in gw.getAllWindows():
            if "kindle" in win.title.lower() and win.title.strip():
                windows.append(win.title)
        self.kindle_combo["values"] = windows if windows else ["（Kindleが見つかりません）"]
        if windows:
            self.kindle_combo.current(0)
        else:
            self.kindle_var.set("（Kindleが見つかりません）")

    def _get_kindle_window(self):
        title = self.kindle_var.get()
        for win in gw.getAllWindows():
            if win.title == title:
                return win
        return None

    # ============================================================
    # フォルダ選択
    # ============================================================
    def _browse_folder(self):
        folder = filedialog.askdirectory(title="保存先フォルダを選択")
        if folder:
            self.folder_var.set(folder)

    # ============================================================
    # ログ出力
    # ============================================================
    def _log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"

        def _append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", line)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        self.root.after(0, _append)

    def _update_status(self, text: str):
        self.root.after(0, lambda: self.status_var.set(text))

    def _update_progress(self, current: int, total: int):
        pct = (current / total) * 100 if total > 0 else 0
        self.root.after(0, lambda: self.progress_var.set(pct))

    # ============================================================
    # 開始・停止・一時停止
    # ============================================================
    def _on_start(self):
        # バリデーション
        kindle_win = self._get_kindle_window()
        if kindle_win is None:
            messagebox.showerror("エラー", "Kindle for PCのウィンドウが見つかりません。\n起動して本を開いた状態で「更新」を押してください。")
            return

        folder = Path(self.folder_var.get())
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror("エラー", f"フォルダを作成できません:\n{e}")
            return

        self.is_running = True
        self.is_paused = False
        self.captured_count = 0

        self.btn_start.configure(state="disabled")
        self.btn_pause.configure(state="normal")
        self.btn_stop.configure(state="normal")

        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()

    def _on_pause(self):
        if self.is_paused:
            self.is_paused = False
            self.btn_pause.configure(text="⏸ 一時停止")
            self._log("再開しました")
            self._update_status("キャプチャ中...")
        else:
            self.is_paused = True
            self.btn_pause.configure(text="▶ 再開")
            self._log("一時停止しました")
            self._update_status("一時停止中")

    def _on_stop(self):
        self.is_running = False
        self._log("停止を要求しました")

    def _finish(self):
        self.is_running = False
        self.root.after(0, lambda: self.btn_start.configure(state="normal"))
        self.root.after(0, lambda: self.btn_pause.configure(state="disabled", text="⏸ 一時停止"))
        self.root.after(0, lambda: self.btn_stop.configure(state="disabled"))

    # ============================================================
    # キャプチャループ（別スレッドで実行）
    # ============================================================
    def _capture_loop(self):
        total_pages = self.pages_var.get()
        start_num = self.start_num_var.get()
        countdown = self.countdown_var.get()
        page_wait = self.wait_var.get()
        folder = Path(self.folder_var.get())
        prefix = self.prefix_var.get()
        quality = self.quality_var.get()
        crop_toolbar = self.crop_toolbar_var.get()

        # カウントダウン
        for sec in range(countdown, 0, -1):
            if not self.is_running:
                self._finish()
                return
            self._update_status(f"開始まで {sec} 秒... Kindleの画面を前面にしてください")
            self._log(f"開始まで {sec} 秒...")
            time.sleep(1)

        self._log(f"キャプチャ開始: {total_pages}ページ")

        for i in range(total_pages):
            # 停止チェック
            if not self.is_running:
                break

            # 一時停止チェック
            while self.is_paused and self.is_running:
                time.sleep(0.3)

            if not self.is_running:
                break

            page_num = start_num + i
            self._update_status(f"キャプチャ中: {i + 1}/{total_pages} (番号: {page_num:04d})")
            self._update_progress(i, total_pages)

            # Kindleウィンドウ取得
            kindle_win = self._get_kindle_window()
            if kindle_win is None:
                self._log("ERROR: Kindleウィンドウが見つかりません。停止します。")
                break

            # ウィンドウを前面に
            try:
                kindle_win.activate()
            except Exception:
                pass
            time.sleep(0.3)

            # スクリーンショット取得
            try:
                left = kindle_win.left
                top = kindle_win.top
                width = kindle_win.width
                height = kindle_win.height

                # ツールバー除外
                if crop_toolbar:
                    crop_top = 80
                    top += crop_top
                    height -= crop_top

                screenshot = pyautogui.screenshot(region=(left, top, width, height))

                # JPEG保存
                filename = f"{prefix}_{page_num:04d}.jpg"
                filepath = folder / filename
                screenshot.save(filepath, "JPEG", quality=quality)

                self.captured_count += 1
                self._log(f"保存: {filename}  ({width}x{height})")

            except Exception as e:
                self._log(f"ERROR (ページ{page_num}): {e}")

            # 最終ページでなければページ送り
            if i < total_pages - 1:
                pyautogui.press("right")
                time.sleep(page_wait)

        # 完了
        self._update_progress(total_pages, total_pages)
        self._log(f"完了！ {self.captured_count}枚の画像を保存しました → {folder}")
        self._update_status(f"完了: {self.captured_count}枚保存済み")
        self._finish()

        # 保存先フォルダを開く
        if self.captured_count > 0:
            try:
                os.startfile(str(folder))
            except Exception:
                pass


# ============================================================
# エントリーポイント
# ============================================================
def main():
    root = tk.Tk()
    app = KindleCaptureApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
