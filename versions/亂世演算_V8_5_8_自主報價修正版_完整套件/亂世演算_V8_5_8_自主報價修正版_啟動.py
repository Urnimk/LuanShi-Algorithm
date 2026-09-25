import os
import json
import re
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import glob
import importlib.util
from experience_view import render_current_q

try:
    from 亂世演算_V8_5_8_自主報價修正版 import (
        thread_stat_monitor,
        toggle_simulation_paused,
        request_simulation_step,
        set_simulation_speed,
        get_simulation_control_state,
        save_path,
        current_strategic_state,
        STRATEGIC_ACTIONS,
    )
except ModuleNotFoundError:
    # 下載同名版本可能被系統加上 (1)/(2)/(3)，啟動器自動載入同目錄最新引擎。
    pattern = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "亂世演算_V8_5_8_自主報價修正版*.py",
    )
    candidates = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    if not candidates:
        raise
    spec = importlib.util.spec_from_file_location("亂世演算_v85_engine", candidates[0])
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    thread_stat_monitor = engine.thread_stat_monitor
    toggle_simulation_paused = engine.toggle_simulation_paused
    request_simulation_step = engine.request_simulation_step
    set_simulation_speed = engine.set_simulation_speed
    get_simulation_control_state = engine.get_simulation_control_state
    save_path = engine.save_path
    current_strategic_state = engine.current_strategic_state
    STRATEGIC_ACTIONS = engine.STRATEGIC_ACTIONS

# ==============================================================================
# ⚙️ 全域 UI 與系統參數設定 (Global Configuration)
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. 視窗與定時器設定
# ------------------------------------------------------------------------------
# 主視窗頂部標題列所顯示的文字名稱
WINDOW_TITLE = "亂世演算 V8_5_8｜自主報價修正版"

# 應用程式啟動時的預設視窗解析度 (寬度x高度，單位：像素)
WINDOW_SIZE = "1500x900"

# 背景 UI 定時器自動抓取檔案與刷新的時間間隔 (單位：毫秒，1500ms = 1.5 秒)
REFRESH_INTERVAL_MS = 1500

# 右下角「全域即時戰鬥 LOG」視窗最多讀取並顯示的最新日誌行數上限
MAX_GLOBAL_LOG_LINES = 25

# 左側「國家詳細查詢」與「聯盟詳細查詢」分頁中，下方專屬 LOG 視窗顯示的歷史事件最大筆數
MAX_SPECIFIC_LOG_LINES = 10


# ------------------------------------------------------------------------------
# 2. 字型名稱與字體大小設定
# ------------------------------------------------------------------------------
# 介面主要文字與標籤使用的預設字體 family (微軟正黑體)
FONT_FAMILY_MAIN = "Microsoft JhengHei"

# 排版需要等寬對齊時 (如世界即時排名) 所採用的 monospace 字體 family
FONT_FAMILY_MONO = "Consolas"


# 下拉選單、提示標籤等通用 UI 元件的文字級階大小
FONT_SIZE_UI = 12

# 表格 (Treeview) 頂部欄位標題與標題框 (LabelFrame) 的文字大小
FONT_SIZE_HEADER = 12

# 國家與聯盟詳細資訊文本框 (Text Area) 內部內文的文字大小
FONT_SIZE_DETAIL = 12

# 右上角世界即時排名列表區塊的文字大小
FONT_SIZE_RANK = 12

# 所有事件日誌 (LOG) 區域的文字大小
FONT_SIZE_LOG = 12

# 國家與聯盟詳細資訊欄位內容字體大小
CONFIGURE_FONT = 14


# 封裝一般 UI 元件使用的標準字型設定 (字體, 字號)
FONT_UI_NORMAL = (FONT_FAMILY_MAIN, FONT_SIZE_UI)

# 封裝一般 UI 元件使用的粗體字型設定 (字體, 字號, 粗體)
FONT_UI_BOLD = (FONT_FAMILY_MAIN, FONT_SIZE_UI, "bold")

# 封裝標題欄位與區塊標題使用的粗體字型設定
FONT_HEADER_BOLD = (FONT_FAMILY_MAIN, FONT_SIZE_HEADER, "bold")

# 封裝詳細查詢內文區域使用的標準字型設定
FONT_DETAIL_TEXT = (FONT_FAMILY_MAIN, FONT_SIZE_DETAIL)

# 封裝世界排名文字區塊使用的等寬字型設定
FONT_RANK_MONO = (FONT_FAMILY_MONO, FONT_SIZE_RANK)

# 封裝事件日誌區域使用的標準字型設定
FONT_LOG_TEXT = (FONT_FAMILY_MAIN, FONT_SIZE_LOG)

# 封裝事件日誌區域內部重點高亮使用的粗體字型設定
FONT_LOG_BOLD = (FONT_FAMILY_MAIN, FONT_SIZE_LOG, "bold")


# ------------------------------------------------------------------------------
# 3. 顏色主題設定 (十六進位 RGB 顏色碼)
# ------------------------------------------------------------------------------
# 主視窗與大多數容器背景的底色 (深灰近黑)
COLOR_BG_MAIN = "#1E1E1E"

# 事件 LOG 輸入框等更深層區塊的背景顏色 (極深灰)
COLOR_BG_DARK = "#181818"

# 文本輸入框、列表格 (Treeview) 與下拉選單等數據展示區的背景色 (暗灰)
COLOR_BG_FIELD = "#252526"

# 左側分頁標籤 (Notebook Tab) 未選取時的背景顏色
COLOR_BG_TAB = "#2D2D2D"

# 左側分頁標籤 (Notebook Tab) 當前被選中時的高亮背景顏色 (經典 VSCode 藍)
COLOR_BG_TAB_ACTIVE = "#007ACC"

# 表格 (Treeview) 頂部欄位 Header 的背景顏色
COLOR_BG_HEADER = "#333333"


# 一般主要標題與高亮文字的文字顏色 (純白)
COLOR_FG_WHITE = "#FFFFFF"

# 未選中的分頁頁籤或次要內容的文字顏色 (淺灰)
COLOR_FG_MUTED = "#CCCCCC"

# 標準內文與一般日誌文字的預設前景色 (灰白)
COLOR_FG_TEXT = "#D4D4D4"

# 世界即時排名內文的預設前景色 (明亮灰)
COLOR_FG_RANK = "#DCDCDC"

# 區塊外框標題與重點強調標籤的前景色 (天藍)
COLOR_FG_ACCENT = "#007ACC"

# 世界排名中標示聯盟名稱高亮的前景色 (明亮黃)
COLOR_FG_YELLOW = "#FFE066"


# ------------------------------------------------------------------------------
# 4. 表格欄位寬度設定 (單位：像素)
# ------------------------------------------------------------------------------
# 國家總覽列表中，「國家名稱」欄位的預設顯示寬度
COL_WIDTH_COUNTRY_NAME = 120

# 國家總覽列表中，「世代」欄位的預設顯示寬度
COL_WIDTH_COUNTRY_GEN = 50

# 國家總覽列表中，「戰力」欄位的預設顯示寬度
COL_WIDTH_COUNTRY_POWER = 80

# 國家總覽列表中，「總人口」欄位的預設顯示寬度
COL_WIDTH_COUNTRY_POP = 70

# 國家總覽列表中，「士兵」欄位的預設顯示寬度
COL_WIDTH_COUNTRY_SOLDIERS = 60

# 國家總覽列表中，「糧草」欄位的預設顯示寬度
COL_WIDTH_COUNTRY_FOOD = 70

# 國家總覽列表中，「狀態 (存活/滅亡)」欄位的預設顯示寬度
COL_WIDTH_COUNTRY_STATUS = 60


# 聯盟總覽列表中，「聯盟名稱」欄位的預設顯示寬度
COL_WIDTH_ALLIANCE_NAME = 150

# 聯盟總覽列表中，「總戰力」欄位的預設顯示寬度
COL_WIDTH_ALLIANCE_POWER = 90

# 聯盟總覽列表中，「成員數量」欄位的預設顯示寬度
COL_WIDTH_ALLIANCE_MEMBERS = 80

# 聯盟總覽列表中，「圍剿目標」欄位的預設顯示寬度
COL_WIDTH_ALLIANCE_TARGET = 120

# ==============================================================================


class GameInterfaceUI:
    def __init__(self, root):
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_SIZE)
        self.root.configure(bg=COLOR_BG_MAIN)

        # 樣式設定
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(".", background=COLOR_BG_MAIN, foreground=COLOR_FG_WHITE, fieldbackground=COLOR_BG_FIELD)
        self.style.configure("TNotebook", background=COLOR_BG_MAIN)
        self.style.configure("TNotebook.Tab", background=COLOR_BG_TAB, foreground=COLOR_FG_MUTED, padding=[8, 5])
        self.style.map("TNotebook.Tab", background=[("selected", COLOR_BG_TAB_ACTIVE)], foreground=[("selected", COLOR_FG_WHITE)])
        self.style.configure(
            "Treeview",
            background=COLOR_BG_FIELD,
            foreground=COLOR_FG_WHITE,
            fieldbackground=COLOR_BG_FIELD,
            font=(FONT_FAMILY_MAIN, CONFIGURE_FONT),
            rowheight=30,
        )
        self.style.configure("Treeview.Heading", background=COLOR_BG_HEADER, foreground=COLOR_FG_WHITE, font=FONT_HEADER_BOLD)

        # 主網格佈局
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # ----------------------------------------------------
        # ⬅️ 左側分頁區域
        #    國家總覽 / 聯盟總覽 / 國家詳細查詢 / 聯盟詳細查詢
        #
        # V6.6.1：
        # 「國家詳細資訊」與「國家編年史」都顯示在左半側；
        # 右半側固定保留世界排名與即時 LOG。
        # ----------------------------------------------------
        self.left_notebook = ttk.Notebook(self.root)
        self.left_notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # 1. 🌐 國家總覽 Tab
        self.tab_country = ttk.Frame(self.left_notebook)
        self.left_notebook.add(self.tab_country, text=" 🌐 國家總覽 ")
        
        self.tree_country = ttk.Treeview(
            self.tab_country, 
            # columns=("name", "gen", "power", "pop", "soldiers", "championship_count", "status"),
            columns=("name", "gen", "power", "pop", "gold", "championship_count", "status"),    
            show="headings"
        )
        self.tree_country.column("name", width=COL_WIDTH_COUNTRY_NAME, anchor="w")
        self.tree_country.column("gen", width=COL_WIDTH_COUNTRY_GEN, anchor="center")
        self.tree_country.column("power", width=COL_WIDTH_COUNTRY_POWER, anchor="e")
        self.tree_country.column("pop", width=COL_WIDTH_COUNTRY_POP, anchor="e")
        # self.tree_country.column("soldiers", width=COL_WIDTH_COUNTRY_SOLDIERS, anchor="e")
        self.tree_country.column("gold", width=COL_WIDTH_COUNTRY_SOLDIERS, anchor="e")
        self.tree_country.column("championship_count", width=COL_WIDTH_COUNTRY_FOOD, anchor="center")
        # self.tree_country.column("food", width=COL_WIDTH_COUNTRY_FOOD, anchor="e")
        self.tree_country.column("status", width=COL_WIDTH_COUNTRY_STATUS, anchor="center")

        country_scroll = ttk.Scrollbar(self.tab_country, orient="vertical", command=self.tree_country.yview)
        self.tree_country.configure(yscrollcommand=country_scroll.set)
        self.tree_country.pack(side="left", fill="both", expand=True)
        country_scroll.pack(side="right", fill="y")

        # 2. 🤝 聯盟總覽 Tab
        self.tab_alliance = ttk.Frame(self.left_notebook)
        self.left_notebook.add(self.tab_alliance, text=" 🤝 聯盟總覽 ")

        self.tree_alliance = ttk.Treeview(
            self.tab_alliance, 
            columns=("ally_name", "power", "members", "target"), 
            show="headings"
        )
        self.tree_alliance.column("ally_name", width=COL_WIDTH_ALLIANCE_NAME, anchor="w")
        self.tree_alliance.column("power", width=COL_WIDTH_ALLIANCE_POWER, anchor="e")
        self.tree_alliance.column("members", width=COL_WIDTH_ALLIANCE_MEMBERS, anchor="center")
        self.tree_alliance.column("target", width=COL_WIDTH_ALLIANCE_TARGET, anchor="w")

        alliance_scroll = ttk.Scrollbar(self.tab_alliance, orient="vertical", command=self.tree_alliance.yview)
        self.tree_alliance.configure(yscrollcommand=alliance_scroll.set)
        self.tree_alliance.pack(side="left", fill="both", expand=True)
        alliance_scroll.pack(side="right", fill="y")
        
        # 國家／聯盟總覽支援直接點擊名稱跳到對應詳細資訊。
        # 單擊僅在「名稱欄」生效；雙擊整列仍可快速開啟詳細資料。
        self.tree_country.bind("<ButtonRelease-1>", self.on_country_tree_click)
        self.tree_alliance.bind("<ButtonRelease-1>", self.on_alliance_tree_click)

        # ----------------------------------------------------
        # 3. 🔍 單一國家詳細查詢 Tab
        # ----------------------------------------------------
        self.tab_detail = ttk.Frame(self.left_notebook)
        self.left_notebook.add(
            self.tab_detail,
            text=" 🔍 國家詳細查詢 ",
        )

        # 詳細資訊與編年史共用左側同一個 Tab；
        # 「📜 編年史」與「← 詳細資訊」按鈕互相切換。
        self.country_detail_stack = tk.Frame(
            self.tab_detail,
            bg=COLOR_BG_MAIN,
        )
        self.country_detail_stack.pack(
            fill="both",
            expand=True,
        )
        self.country_detail_stack.grid_rowconfigure(0, weight=1)
        self.country_detail_stack.grid_columnconfigure(0, weight=1)

        self.country_detail_page = ttk.Frame(
            self.country_detail_stack,
        )
        self.country_detail_page.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.select_frame = tk.Frame(
            self.country_detail_page,
            bg=COLOR_BG_MAIN,
        )
        self.select_frame.pack(fill="x", padx=8, pady=(6, 4))

        tk.Label(
            self.select_frame,
            text="選擇國家：",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_WHITE,
            font=FONT_UI_BOLD,
        ).pack(side="left")

        self.country_cb = ttk.Combobox(
            self.select_frame,
            font=FONT_UI_NORMAL,
            state="normal",
        )
        self.country_cb.pack(side="left", padx=5, fill="x", expand=True)
        self.country_cb.bind("<<ComboboxSelected>>", self.on_country_selected)
        self.country_cb.bind("<Return>", self.filter_country_cb)

        # 國家儀表板
        self.country_dashboard = tk.Frame(self.country_detail_page, bg=COLOR_BG_MAIN)
        self.country_dashboard.pack(fill="x", padx=8, pady=(0, 4))
        self.country_dashboard.grid_columnconfigure(0, weight=1)
        self.country_dashboard.grid_columnconfigure(1, weight=1)

        # 左上：基本狀態
        self.country_basic_group = tk.LabelFrame(
            self.country_dashboard,
            text=" 🏛️ 基本狀態 ",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_ACCENT,
            font=FONT_UI_BOLD,
        )
        self.country_basic_group.grid(
            row=0, column=0, sticky="nsew", padx=(0, 3), pady=(0, 4)
        )

        self.country_basic_tree = ttk.Treeview(
            self.country_basic_group,
            columns=("item", "value"),
            show="headings",
            height=7,
        )
        self.country_basic_tree.heading("item", text="項目")
        self.country_basic_tree.heading("value", text="內容")
        self.country_basic_tree.column("item", width=145, anchor="w", stretch=False)
        self.country_basic_tree.column("value", width=145, anchor="w", stretch=True)

        # V6.5.1：
        # 「基本狀態」右側保留一個固定快捷按鈕，
        # 點一下就在左側同一個「國家詳細查詢」Tab 切換到編年史。
        self.country_basic_group.grid_rowconfigure(0, weight=1)
        self.country_basic_group.grid_columnconfigure(0, weight=1)

        self.country_basic_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(4, 0),
            pady=4,
        )

        self.country_chronicle_button = ttk.Button(
            self.country_basic_group,
            text="📜 編年史",
            width=9,
            command=self.open_selected_country_chronicle,
        )
        self.country_chronicle_button.grid(
            row=0,
            column=1,
            sticky="ne",
            padx=(4, 4),
            # 對齊 Treeview 標題列下方的第一筆「國家狀態」。
            pady=(35, 0),
        )

        self.country_experience_button = ttk.Button(
            self.country_basic_group,
            text="🧠 經驗",
            width=9,
            command=self.open_selected_country_experience,
        )
        self.country_experience_button.grid(
            row=0, column=1, sticky="ne", padx=(4, 4), pady=(72, 0),
        )

        # 右上：人口、建築與資源
        self.country_econ_group = tk.LabelFrame(
            self.country_dashboard,
            text=" 👥 人口・建築・資源 ",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_ACCENT,
            font=FONT_UI_BOLD,
        )
        self.country_econ_group.grid(
            row=0, column=1, sticky="nsew", padx=(3, 0), pady=(0, 4)
        )

        self.country_econ_tree = ttk.Treeview(
            self.country_econ_group,
            columns=("item", "value"),
            show="headings",
            height=7,
        )
        self.country_econ_tree.heading("item", text="項目")
        self.country_econ_tree.heading("value", text="內容")
        self.country_econ_tree.column("item", width=145, anchor="w", stretch=False)
        self.country_econ_tree.column("value", width=145, anchor="w", stretch=True)
        self.country_econ_tree.pack(fill="both", expand=True, padx=4, pady=4)

        # 中間：目前戰爭
        self.country_war_group = tk.LabelFrame(
            self.country_dashboard,
            text=" ⚔️ 當前戰爭 ",
            bg=COLOR_BG_MAIN,
            fg="#FFB86C",
            font=FONT_UI_BOLD,
        )
        self.country_war_group.grid(
            row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 4)
        )

        self.country_war_tree = ttk.Treeview(
            self.country_war_group,
            columns=("war_id", "role", "enemy", "round", "tactic"),
            show="headings",
            height=2,
        )
        for col, title, width, anchor in (
            ("war_id", "戰爭", 70, "center"),
            ("role", "立場", 85, "center"),
            ("enemy", "交戰對象", 165, "w"),
            ("round", "回合", 70, "center"),
            ("tactic", "最近戰術", 105, "center"),
        ):
            self.country_war_tree.heading(col, text=title)
            self.country_war_tree.column(col, width=width, anchor=anchor, stretch=(col == "enemy"))
        self.country_war_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.country_war_tree.bind("<Double-Button-1>", self.on_country_war_double_click)

        # 下方：外交與戰績 + 完整奪冠紀錄
        # 左側放摘要；右側利用原本空間放完整冠軍歷史，可用滑輪/捲軸查看。
        self.country_record_area = tk.Frame(
            self.country_dashboard,
            bg=COLOR_BG_MAIN,
        )
        self.country_record_area.grid(
            row=2, column=0, columnspan=2, sticky="nsew"
        )
        # 左右兩框固定等寬，外交戰績與完整奪冠紀錄各占 50%。
        self.country_record_area.grid_columnconfigure(
            0, weight=1, uniform="country_record_equal"
        )
        self.country_record_area.grid_columnconfigure(
            1, weight=1, uniform="country_record_equal"
        )
        self.country_record_area.grid_rowconfigure(0, weight=1)

        # 左側：外交與戰績摘要
        self.country_record_group = tk.LabelFrame(
            self.country_record_area,
            text=" 🏆 外交・戰績 ",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_ACCENT,
            font=FONT_UI_BOLD,
        )
        self.country_record_group.grid(
            row=0, column=0, sticky="nsew", padx=(0, 3)
        )

        self.country_record_tree = ttk.Treeview(
            self.country_record_group,
            columns=("item", "value"),
            show="headings",
            height=7,
        )
        self.country_record_tree.heading("item", text="項目")
        self.country_record_tree.heading("value", text="內容")
        self.country_record_tree.column(
            "item", width=120, anchor="w", stretch=False
        )
        self.country_record_tree.column(
            "value", width=330, anchor="w", stretch=True
        )
        self.country_record_tree.pack(
            fill="both", expand=True, padx=4, pady=4
        )

        # 右側：完整奪冠紀錄
        self.country_champion_group = tk.LabelFrame(
            self.country_record_area,
            text=" 👑 完整奪冠紀錄 ",
            bg=COLOR_BG_MAIN,
            fg="#FFD700",
            font=FONT_UI_BOLD,
        )
        self.country_champion_group.grid(
            row=0, column=1, sticky="nsew", padx=(3, 0)
        )

        self.country_champion_container = tk.Frame(
            self.country_champion_group,
            bg=COLOR_BG_MAIN,
        )
        self.country_champion_container.pack(
            fill="both", expand=True, padx=4, pady=4
        )

        self.country_champion_tree = ttk.Treeview(
            self.country_champion_container,
            columns=("no", "record"),
            show="headings",
            height=7,
        )
        self.country_champion_tree.heading("no", text="次序")
        self.country_champion_tree.heading("record", text="奪冠紀錄")
        self.country_champion_tree.column(
            "no", width=75, anchor="center", stretch=False
        )
        self.country_champion_tree.column(
            "record", width=360, anchor="w", stretch=True
        )

        self.country_champion_scroll = ttk.Scrollbar(
            self.country_champion_container,
            orient="vertical",
            command=self.country_champion_tree.yview,
        )
        self.country_champion_tree.configure(
            yscrollcommand=self.country_champion_scroll.set
        )

        self.country_champion_tree.pack(
            side="left", fill="both", expand=True
        )
        self.country_champion_scroll.pack(
            side="right", fill="y"
        )

        # 國家事件 LOG：只留最新幾筆，通常不需要滑輪；仍保留必要時可捲動。
        self.country_log_group = tk.LabelFrame(
            self.country_detail_page,
            text=f" 📜 近 {MAX_SPECIFIC_LOG_LINES} 次國家／關聯戰爭事件 ",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_TEXT,
            font=FONT_UI_BOLD,
        )
        self.country_log_group.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.country_log_text = scrolledtext.ScrolledText(
            self.country_log_group,
            bg=COLOR_BG_DARK,
            fg=COLOR_FG_TEXT,
            font=FONT_LOG_TEXT,
            wrap=tk.WORD,
            height=7,
        )
        self.country_log_text.pack(fill="both", expand=True, padx=4, pady=4)

        # 4. 🛡️ 單一聯盟詳細查詢 Tab
        self.tab_ally_detail = ttk.Frame(self.left_notebook)
        self.left_notebook.add(self.tab_ally_detail, text=" 🛡️ 聯盟詳細查詢 ")

        self.ally_select_frame = tk.Frame(self.tab_ally_detail, bg=COLOR_BG_MAIN)
        self.ally_select_frame.pack(fill="x", padx=8, pady=(6, 4))

        tk.Label(
            self.ally_select_frame,
            text="選擇聯盟：",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_WHITE,
            font=FONT_UI_BOLD,
        ).pack(side="left")

        self.ally_cb = ttk.Combobox(
            self.ally_select_frame,
            font=FONT_UI_NORMAL,
            state="normal",
        )
        self.ally_cb.pack(side="left", padx=5, fill="x", expand=True)
        self.ally_cb.bind("<<ComboboxSelected>>", self.on_alliance_selected)
        self.ally_cb.bind("<Return>", self.filter_alliance_cb)

        self.alliance_dashboard = tk.Frame(
            self.tab_ally_detail,
            bg=COLOR_BG_MAIN,
        )
        self.alliance_dashboard.pack(fill="x", padx=8, pady=(0, 4))

        # 聯盟查詢重新整理成：
        # ┌──────────────┬──────────────┐
        # │   聯盟摘要   │  聯盟當前戰爭 │
        # ├──────────────┴──────────────┤
        # │         聯盟成員明細         │
        # └─────────────────────────────┘
        self.alliance_dashboard.grid_columnconfigure(
            0, weight=1, uniform="alliance_top_equal"
        )
        self.alliance_dashboard.grid_columnconfigure(
            1, weight=1, uniform="alliance_top_equal"
        )
        self.alliance_dashboard.grid_rowconfigure(0, weight=1)

        # ----------------------------------------------------
        # 左上：聯盟摘要
        # ----------------------------------------------------
        self.alliance_summary_group = tk.LabelFrame(
            self.alliance_dashboard,
            text=" 🛡️ 聯盟摘要 ",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_ACCENT,
            font=FONT_UI_BOLD,
        )
        self.alliance_summary_group.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 3),
            pady=(0, 4),
        )

        self.alliance_summary_tree = ttk.Treeview(
            self.alliance_summary_group,
            columns=("item", "value"),
            show="headings",
            height=6,
        )
        self.alliance_summary_tree.heading("item", text="項目")
        self.alliance_summary_tree.heading("value", text="內容")
        self.alliance_summary_tree.column(
            "item", width=115, anchor="w", stretch=False
        )
        self.alliance_summary_tree.column(
            "value", width=330, anchor="w", stretch=True
        )
        self.alliance_summary_tree.pack(
            fill="both", expand=True, padx=4, pady=4
        )

        # ----------------------------------------------------
        # 右上：聯盟當前戰爭
        # ----------------------------------------------------
        self.alliance_war_group = tk.LabelFrame(
            self.alliance_dashboard,
            text=" ⚔️ 聯盟當前戰爭（雙擊對手可跳轉） ",
            bg=COLOR_BG_MAIN,
            fg="#FFB86C",
            font=FONT_UI_BOLD,
        )
        self.alliance_war_group.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(3, 0),
            pady=(0, 4),
        )

        self.alliance_war_container = tk.Frame(
            self.alliance_war_group,
            bg=COLOR_BG_MAIN,
        )
        self.alliance_war_container.pack(
            fill="both", expand=True, padx=4, pady=4
        )

        self.alliance_war_tree = ttk.Treeview(
            self.alliance_war_container,
            columns=("war_id", "role", "enemy", "round", "tactic"),
            show="headings",
            height=5,
        )

        for col, title, width, anchor in (
            ("war_id", "戰爭", 68, "center"),
            ("role", "立場", 78, "center"),
            ("enemy", "交戰對象", 170, "w"),
            ("round", "回合", 62, "center"),
            ("tactic", "最近戰術", 95, "center"),
        ):
            self.alliance_war_tree.heading(col, text=title)
            self.alliance_war_tree.column(
                col,
                width=width,
                anchor=anchor,
                stretch=(col == "enemy"),
            )

        self.alliance_war_scroll = ttk.Scrollbar(
            self.alliance_war_container,
            orient="vertical",
            command=self.alliance_war_tree.yview,
        )
        self.alliance_war_tree.configure(
            yscrollcommand=self.alliance_war_scroll.set
        )

        self.alliance_war_tree.pack(
            side="left", fill="both", expand=True
        )
        self.alliance_war_scroll.pack(
            side="right", fill="y"
        )
        self.alliance_war_tree.bind(
            "<Double-Button-1>",
            self.on_alliance_war_double_click,
        )

        # ----------------------------------------------------
        # 下方：聯盟成員明細
        # ----------------------------------------------------
        self.alliance_member_group = tk.LabelFrame(
            self.alliance_dashboard,
            text=" 👥 聯盟成員明細（雙擊國家可直接查詢） ",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_ACCENT,
            font=FONT_UI_BOLD,
        )
        self.alliance_member_group.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="nsew",
        )

        self.alliance_member_container = tk.Frame(
            self.alliance_member_group,
            bg=COLOR_BG_MAIN,
        )
        self.alliance_member_container.pack(
            fill="both", expand=True, padx=4, pady=4
        )

        self.alliance_member_tree = ttk.Treeview(
            self.alliance_member_container,
            # columns=("name", "rank", "power", "pop", "soldiers", "status"),
            columns=("name", "rank", "power", "pop", "gold", "status"),        
            show="headings",
            height=6,
        )

        # 數值欄固定；只有「國家」欄吸收剩餘空間，右側不留白。
        for col, title, width, anchor in (
            ("name",     "國家",  240, "w"),
            ("rank",     "排名",  100, "center"),
            ("power",    "戰力",  155, "center"),
            ("pop",      "人口",  145, "center"),
            # ("soldiers", "士兵",  145, "center"),
            ("gold", "士兵",  145, "center"),
            ("status",   "狀態",  120, "center"),
        ):
            self.alliance_member_tree.heading(col, text=title)
            self.alliance_member_tree.column(
                col,
                width=width,
                minwidth=width,
                anchor=anchor,
                stretch=(col == "name"),
            )

        self.alliance_member_scroll = ttk.Scrollbar(
            self.alliance_member_container,
            orient="vertical",
            command=self.alliance_member_tree.yview,
        )
        self.alliance_member_tree.configure(
            yscrollcommand=self.alliance_member_scroll.set
        )

        self.alliance_member_tree.pack(
            side="left", fill="both", expand=True
        )
        self.alliance_member_scroll.pack(
            side="right", fill="y"
        )

        self.alliance_member_tree.bind(
            "<Double-Button-1>",
            self.on_alliance_member_double_click,
        )

        self.ally_log_group = tk.LabelFrame(
            self.tab_ally_detail,
            text=f" 📜 近 {MAX_SPECIFIC_LOG_LINES} 次聯盟相關事件 ",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_ACCENT,
            font=FONT_UI_BOLD,
        )
        self.ally_log_group.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.ally_log_text = scrolledtext.ScrolledText(
            self.ally_log_group,
            bg=COLOR_BG_DARK,
            fg=COLOR_FG_TEXT,
            font=FONT_LOG_TEXT,
            wrap=tk.WORD,
            height=7,
        )
        self.ally_log_text.pack(fill="both", expand=True, padx=4, pady=4)

        # ----------------------------------------------------
        # 5. 💹 世界報價系統 Tab（位於聯盟詳細資訊右側）
        # ----------------------------------------------------
        self.tab_market = ttk.Frame(self.left_notebook)
        self.left_notebook.add(self.tab_market, text=" 💹 世界報價系統 ")

        self.market_bank_label = tk.Label(
            self.tab_market,
            text="世界銀行：等待市場資料…",
            bg=COLOR_BG_MAIN,
            fg="#FFD700",
            font=FONT_UI_BOLD,
            anchor="w",
        )
        self.market_bank_label.pack(fill="x", padx=8, pady=(7, 4))

        self.market_control_frame = tk.Frame(self.tab_market, bg=COLOR_BG_MAIN)
        self.market_control_frame.pack(fill="x", padx=8, pady=(0, 5))
        self.pause_button = tk.Button(
            self.market_control_frame,
            text="⏸ 暫停",
            command=self.toggle_pause,
            bg=COLOR_BG_HEADER,
            fg=COLOR_FG_WHITE,
            font=FONT_UI_BOLD,
        )
        self.pause_button.pack(side="left", padx=(0, 5))
        tk.Button(
            self.market_control_frame,
            text="⏭ 單步",
            command=request_simulation_step,
            bg=COLOR_BG_HEADER,
            fg=COLOR_FG_WHITE,
            font=FONT_UI_BOLD,
        ).pack(side="left", padx=(0, 8))
        tk.Label(self.market_control_frame, text="速度", bg=COLOR_BG_MAIN, fg=COLOR_FG_TEXT, font=FONT_UI_NORMAL).pack(side="left")
        self.speed_cb = ttk.Combobox(
            self.market_control_frame,
            values=("0.1 秒", "0.5 秒", "1 秒", "2 秒", "5 秒"),
            state="readonly",
            width=8,
            font=FONT_UI_NORMAL,
        )
        self.speed_cb.set("2 秒")
        self.speed_cb.pack(side="left", padx=5)
        self.speed_cb.bind("<<ComboboxSelected>>", self.on_speed_changed)
        self.market_stats_label = tk.Label(
            self.tab_market,
            text="市場品質：等待資料…",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_MUTED,
            font=FONT_UI_NORMAL,
            anchor="w",
        )
        self.market_stats_label.pack(fill="x", padx=8, pady=(0, 5))

        self.market_quote_group = tk.LabelFrame(
            self.tab_market,
            text=" 📊 即時資源報價 ",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_ACCENT,
            font=FONT_UI_BOLD,
        )
        self.market_quote_group.pack(fill="x", padx=8, pady=(0, 5))

        self.market_quote_tree = ttk.Treeview(
            self.market_quote_group,
            columns=("resource", "last", "vwap", "bid", "ask", "spread", "buy_qty", "sell_qty", "volume"),
            show="headings",
            height=3,
        )
        for col, title, width, anchor in (
            ("resource", "資源", 110, "center"),
            ("last", "最新價", 110, "center"),
            ("vwap", "均價", 110, "center"),
            ("bid", "最佳買價", 110, "center"),
            ("ask", "最佳賣價", 110, "center"),
            ("spread", "價差", 110, "center"),
            ("buy_qty", "買量", 110, "center"),
            ("sell_qty", "賣量", 110, "center"),
            ("volume", "累計成交", 110, "center"),
        ):
            self.market_quote_tree.heading(col, text=title)
            self.market_quote_tree.column(col, width=width, anchor=anchor, stretch=(col == "resource"))
        self.market_quote_tree.pack(fill="x", expand=True, padx=4, pady=4)

        self.market_order_group = tk.LabelFrame(
            self.tab_market,
            text=" 🧾 掛牌委託簿 ",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_ACCENT,
            font=FONT_UI_BOLD,
        )
        self.market_order_group.pack(fill="both", expand=True, padx=8, pady=(0, 5))

        self.market_order_tree = ttk.Treeview(
            self.market_order_group,
            columns=("side", "country", "resource", "qty", "price", "turn"),
            show="headings",
            height=10,
        )
        for col, title, width, anchor in (
            ("side", "買/賣", 110, "center"),
            ("country", "國家", 110, "center"),
            ("resource", "資源", 110, "center"),
            ("qty", "數量", 110, "center"),
            ("price", "單價(大洋)", 110, "center"),
            ("turn", "掛牌年", 110, "center"),
        ):
            self.market_order_tree.heading(col, text=title)
            self.market_order_tree.column(col, width=width, anchor=anchor, stretch=(col == "country"))
        self.market_order_tree.pack(fill="both", expand=True, padx=4, pady=4)

        self.market_trade_group = tk.LabelFrame(
            self.tab_market,
            text=" 💱 最近成交 ",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_ACCENT,
            font=FONT_UI_BOLD,
        )
        self.market_trade_group.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.market_trade_tree = ttk.Treeview(
            self.market_trade_group,
            columns=("turn", "resource", "qty", "price", "buyer", "seller"),
            show="headings",
            height=7,
        )
        for col, title, width, anchor in (
            ("turn", "年份", 70, "center"),
            ("resource", "資源", 70, "center"),
            ("qty", "數量", 70, "center"),
            ("price", "成交價", 80, "center"),
            ("buyer", "買方", 170, "center"),
            ("seller", "賣方", 170, "center"),
        ):
            self.market_trade_tree.heading(col, text=title)
            self.market_trade_tree.column(col, width=width, anchor=anchor, stretch=(col in {"buyer", "seller"}))
        self.market_trade_tree.pack(fill="both", expand=True, padx=4, pady=4)

        # ----------------------------------------------------
        # ➡️ 右半側：固定顯示即時戰局
        #    國家詳細資訊與編年史都不再覆蓋右半側。
        # ----------------------------------------------------
        self.right_frame = tk.Frame(
            self.root,
            bg=COLOR_BG_MAIN,
        )
        self.right_frame.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(0, 10),
            pady=10,
        )
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(1, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        self.rank_group = tk.LabelFrame(
            self.right_frame,
            text=" 🏆 世界即時排名 (點擊名稱自動查詢) ",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_ACCENT,
            font=FONT_UI_BOLD,
        )
        self.rank_group.grid(
            row=0,
            column=0,
            sticky="nsew",
            pady=(0, 5),
        )

        self.rank_text = scrolledtext.ScrolledText(
            self.rank_group,
            bg=COLOR_BG_FIELD,
            fg=COLOR_FG_RANK,
            font=FONT_RANK_MONO,
            wrap=tk.WORD,
        )
        self.rank_text.pack(
            fill="both",
            expand=True,
            padx=5,
            pady=5,
        )

        self.log_group = tk.LabelFrame(
            self.right_frame,
            text=" ⚔️ 即時戰鬥與事件 LOG ",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_ACCENT,
            font=FONT_UI_BOLD,
        )
        self.log_group.grid(
            row=1,
            column=0,
            sticky="nsew",
            pady=(5, 0),
        )

        self.log_text = scrolledtext.ScrolledText(
            self.log_group,
            bg=COLOR_BG_DARK,
            fg=COLOR_FG_TEXT,
            font=FONT_LOG_TEXT,
            wrap=tk.WORD,
        )
        self.log_text.pack(
            fill="both",
            expand=True,
            padx=5,
            pady=5,
        )

        # ----------------------------------------------------
        # ⬅️ 左半側：國家編年史
        #    不新增獨立 Tab；由「國家詳細查詢」中的 📜 編年史按鈕進入。
        # ----------------------------------------------------
        self.chronicle_page = tk.Frame(
            self.country_detail_stack,
            bg=COLOR_BG_MAIN,
        )
        self.chronicle_page.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.chronicle_top = tk.Frame(
            self.chronicle_page,
            bg=COLOR_BG_MAIN,
        )
        self.chronicle_top.pack(
            fill="x",
            padx=8,
            pady=(6, 5),
        )

        # 使用者指定：編年史一定要能返回同一國家的詳細資訊。
        self.chronicle_back_button = ttk.Button(
            self.chronicle_top,
            text="← 詳細資訊",
            command=self.return_to_country_detail,
        )
        self.chronicle_back_button.pack(
            side="left",
            padx=(0, 10),
        )

        tk.Label(
            self.chronicle_top,
            text="選擇國家：",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_WHITE,
            font=FONT_UI_BOLD,
        ).pack(side="left")

        self.chronicle_country_cb = ttk.Combobox(
            self.chronicle_top,
            font=FONT_UI_NORMAL,
            state="normal",
        )
        self.chronicle_country_cb.pack(
            side="left",
            padx=(5, 10),
            fill="x",
            expand=True,
        )
        self.chronicle_country_cb.bind(
            "<<ComboboxSelected>>",
            self.on_chronicle_country_selected,
        )
        self.chronicle_country_cb.bind(
            "<Return>",
            self.on_chronicle_country_selected,
        )

        self.chronicle_year_label = tk.Label(
            self.chronicle_top,
            text="世界曆：第 1 年",
            bg=COLOR_BG_MAIN,
            fg="#FFD700",
            font=FONT_UI_BOLD,
        )
        self.chronicle_year_label.pack(side="right")

        self.chronicle_summary_label = tk.Label(
            self.chronicle_page,
            text="",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_TEXT,
            font=FONT_UI_NORMAL,
            anchor="w",
        )
        self.chronicle_summary_label.pack(
            fill="x",
            padx=10,
            pady=(0, 5),
        )

        self.chronicle_group = tk.LabelFrame(
            self.chronicle_page,
            text=" 📖 歷代國家編年史 ",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_ACCENT,
            font=FONT_UI_BOLD,
        )
        self.chronicle_group.pack(
            fill="both",
            expand=True,
            padx=8,
            pady=(0, 8),
        )

        self.chronicle_table_frame = tk.Frame(
            self.chronicle_group,
            bg=COLOR_BG_MAIN,
        )
        self.chronicle_table_frame.pack(
            fill="both",
            expand=True,
            padx=4,
            pady=4,
        )

        chronicle_columns = (
            "generation",
            "name",
            "regime_type",
            # "personality",
            "start_year",
            "end_year",
            "duration",
            "end_reason",
            "peak_power",
        )

        self.chronicle_tree = ttk.Treeview(
            self.chronicle_table_frame,
            columns=chronicle_columns,
            show="headings",
        )

        chronicle_specs = (
            ("generation", "世代", 60, "center"),
            ("name", "國名", 180, "center"),
            ("regime_type", "政權類型", 100, "center"),
            # ("personality", "國家性格", 100, "center"),
            ("start_year", "建立年份", 100, "center"),
            ("end_year", "結束年份", 100, "center"),
            ("duration", "維持", 100, "center"),
            ("end_reason", "結束原因", 180, "center"),
            ("peak_power", "最高戰力（年份）", 200, "center"),  # w:前置  e:後製  center:置中
        )

        for col, title, width, anchor in chronicle_specs:
            self.chronicle_tree.heading(
                col,
                text=title,
            )
            self.chronicle_tree.column(
                col,
                width=width,
                minwidth=60,
                anchor=anchor,
                stretch=(col in {"peak_power"}),
            )

        self.chronicle_vscroll = ttk.Scrollbar(
            self.chronicle_table_frame,
            orient="vertical",
            command=self.chronicle_tree.yview,
        )
        self.chronicle_hscroll = ttk.Scrollbar(
            self.chronicle_table_frame,
            orient="horizontal",
            command=self.chronicle_tree.xview,
        )
        self.chronicle_tree.configure(
            yscrollcommand=self.chronicle_vscroll.set,
            xscrollcommand=self.chronicle_hscroll.set,
        )

        self.chronicle_table_frame.grid_rowconfigure(0, weight=1)
        self.chronicle_table_frame.grid_columnconfigure(0, weight=1)

        self.chronicle_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        self.chronicle_vscroll.grid(
            row=0,
            column=1,
            sticky="ns",
        )
        self.chronicle_hscroll.grid(
            row=1,
            column=0,
            sticky="ew",
        )

        self.chronicle_tree.tag_configure(
            "current",
            background="#15324A",
        )

        # 經驗頁與詳細資訊及編年史使用同一個國家查詢分頁。
        self.experience_page = tk.Frame(self.country_detail_stack, bg=COLOR_BG_MAIN)
        self.experience_page.grid(row=0, column=0, sticky="nsew")
        experience_toolbar = tk.Frame(self.experience_page, bg=COLOR_BG_MAIN)
        experience_toolbar.pack(fill="x", padx=8, pady=(6, 5))
        ttk.Button(experience_toolbar, text="← 詳細資訊",
                   command=self.return_from_country_experience).pack(side="left", padx=(0, 10))
        self.experience_title = tk.Label(
            experience_toolbar, text="國家經驗｜戰略 Q 值", bg=COLOR_BG_MAIN,
            fg=COLOR_FG_ACCENT, font=FONT_UI_BOLD,
        )
        self.experience_title.pack(side="left")
        ttk.Button(experience_toolbar, text="更新",
                   command=self.refresh_country_experience).pack(side="right")
        self.experience_text = scrolledtext.ScrolledText(
            self.experience_page, wrap="none", bg=COLOR_BG_FIELD,
            fg=COLOR_FG_WHITE, font=FONT_UI_NORMAL,
        )
        self.experience_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.experience_text.configure(state="disabled")
        self.experience_country_key = None

        # 「國家詳細查詢」Tab 初次進入時先顯示詳細資訊。
        self.country_detail_page.tkraise()

        self.setup_rich_log_tags(self.log_text)
        self.setup_rich_log_tags(self.country_log_text)
        self.setup_rich_log_tags(self.ally_log_text)

        self.raw_countries_data = {}
        self.raw_alliances_data = {}
        # 戰國模式進行中的正式戰爭
        self.raw_active_wars = {}
        self.raw_world_mode = {
            "code": "NORMAL",
            "name": "平常局勢",
            "remaining_turns": 0,
        }
        self.raw_world_bank = {}
        self.raw_world_market = {"orders": [], "stats": {}, "recent_trades": []}
        self.engine_version = ""
        self.raw_turn_counter = 0
        self._country_table_signature = None
        self._chronicle_signature = None
        self._alliance_table_signature = None
        self._global_log_cache = None

        # 專屬 LOG 顯示快取：
        # UI 每 1.5 秒刷新一次，但若內容沒變就不要清空/重畫，
        # 否則使用者正在閱讀或捲動時畫面會一直跳回頂端。
        self._specific_log_cache = {}
        self._last_country_log_owner = None
        self._last_alliance_log_owner = None

        # 所有文字資訊區都套用同一套「實體名稱超連結」機制。
        # 不論名稱出現在排名、全域 LOG、詳細資訊或專屬 LOG，都可直接點擊跳轉。
        self.entity_text_widgets = (
            self.rank_text,
            self.log_text,
            self.country_log_text,
            self.ally_log_text,
        )
        for widget in self.entity_text_widgets:
            self.setup_entity_link_widget(widget)

        # 1. 初始化排序狀態變數 (預設依戰力降冪)
        self.country_sort_state = ("power", True)
        self.alliance_sort_state = ("power", True)

        # 2. 綁定國家與聯盟的標題點擊排序事件
        columns_country = [
            ("name", "國家名稱"), ("gen", "國家世代"), ("power", "戰力"),
            # ("pop", "總人口"), ("soldiers", "士兵"), ("championship_count", "冠軍數"), ("status", "狀態")
            ("pop", "總人口"), ("gold", "大洋"), ("championship_count", "冠軍數"), ("status", "狀態")    
        ]
        for col_id, col_name in columns_country:
            self.tree_country.heading(
                col_id, 
                text=col_name, 
                command=lambda c=col_id: self.on_header_click(self.tree_country, c)
            )

        columns_alliance = [
            ("ally_name", "聯盟名稱"), ("power", "總戰力"),
            ("members", "成員數量"), ("target", "圍剿目標")
        ]
        for col_id, col_name in columns_alliance:
            self.tree_alliance.heading(
                col_id, 
                text=col_name, 
                command=lambda c=col_id: self.on_header_click(self.tree_alliance, c)
            )

        # 3. 啟動定時數據刷新
        self.update_ui_data()

    def resolve_country_key(self, name):
        """把國家內部 key、display_name 或畫面文字解析成真正的 countries key。"""
        if not name:
            return None

        name = str(name).strip()
        if name in self.raw_countries_data:
            return name

        # 某些世代／復活情況 display_name 可能與 dictionary key 不同。
        for key, data in self.raw_countries_data.items():
            if str(data.get("display_name", key)).strip() == name:
                return key
        return None

    def resolve_alliance_name(self, name):
        """將畫面上的聯盟名稱解析成 raw_alliances_data 的真正 key。"""
        if not name:
            return None
        name = str(name).strip()
        return name if name in self.raw_alliances_data else None

    def navigate_to_country(self, country_name):
        """選定國家後，切到左側「國家詳細查詢」並顯示完整資訊。"""
        country_key = self.resolve_country_key(country_name)
        if not country_key:
            return False

        self.country_cb.set(country_key)
        self.on_country_selected()
        self.country_detail_page.tkraise()
        self.left_notebook.select(self.tab_detail)
        return True

    def navigate_to_alliance(self, alliance_name):
        """切換到指定聯盟的詳細資訊頁。"""
        ally_key = self.resolve_alliance_name(alliance_name)
        if not ally_key:
            return False

        self.left_notebook.select(self.tab_ally_detail)
        self.ally_cb.set(ally_key)
        self.on_alliance_selected()
        return True

    def on_country_tree_click(self, event):
        """國家總覽：點國家名稱（或雙擊該列）直接進入國家詳細資訊。"""
        row_id = self.tree_country.identify_row(event.y)
        if not row_id:
            return

        column_id = self.tree_country.identify_column(event.x)
        # 只有第 1 欄「國家名稱」本身具有導航功能。
        if column_id != "#1":
            return

        item_values = self.tree_country.item(row_id, "values")
        if item_values:
            self.navigate_to_country(item_values[0])

    def on_alliance_tree_click(self, event):
        """聯盟總覽：聯盟名稱可跳聯盟；圍剿目標國名可直接跳該國。"""
        row_id = self.tree_alliance.identify_row(event.y)
        if not row_id:
            return

        item_values = self.tree_alliance.item(row_id, "values")
        if not item_values:
            return

        column_id = self.tree_alliance.identify_column(event.x)

        # 第 1 欄是聯盟名稱。
        if column_id == "#1":
            self.navigate_to_alliance(item_values[0])
            return

        # 第 4 欄是圍剿目標；若它是國家名稱，直接跳到該國。
        if column_id == "#4" and len(item_values) >= 4:
            self.navigate_to_country(item_values[3])
            return

        # 其他數值欄位不進行跳轉，避免只是選取數字時誤切頁。

    def setup_entity_link_widget(self, widget):
        """讓 Text/ScrolledText 內所有國家與聯盟名稱都具有超連結式互動。"""
        widget.tag_config(
            "country_link",
            foreground="#4FC1FF",
            underline=True,
        )
        widget.tag_config(
            "alliance_link",
            foreground=COLOR_FG_YELLOW,
            underline=True,
        )

        # 用實際滑鼠位置解析名稱，因此同一行出現多個國家／聯盟仍能點準。
        widget.bind("<ButtonRelease-1>", self.on_entity_text_click, add="+")
        widget.bind("<Double-Button-1>", self.on_entity_text_click, add="+")
        widget.bind("<Motion>", self.on_entity_text_motion, add="+")
        widget.bind("<Leave>", lambda e, w=widget: w.configure(cursor="xterm"), add="+")

    def get_entity_aliases(self):
        """回傳目前所有可點擊名稱；較長名稱優先，避免短名稱吃掉長名稱。"""
        aliases = []

        for key, data in self.raw_countries_data.items():
            key_text = str(key).strip()
            display_text = str(data.get("display_name", key)).strip()
            if key_text:
                aliases.append((key_text, "country", key))
            if display_text and display_text != key_text:
                aliases.append((display_text, "country", key))

        for ally_name in self.raw_alliances_data.keys():
            ally_text = str(ally_name).strip()
            if ally_text:
                aliases.append((ally_text, "alliance", ally_name))

        # 去除完全重複項目，並先檢查長名稱。
        unique = {}
        for alias, entity_type, entity_key in aliases:
            unique[(alias, entity_type, entity_key)] = (alias, entity_type, entity_key)
        return sorted(unique.values(), key=lambda x: len(x[0]), reverse=True)

    def entity_at_pointer(self, widget, event):
        """
        依滑鼠實際座標找出被點到的國家／聯盟。
        回傳 (entity_type, entity_key, alias)，找不到則回傳 None。
        """
        try:
            index = widget.index(f"@{event.x},{event.y}")
            line_no, col_no = map(int, index.split("."))
            line_text = widget.get(f"{line_no}.0", f"{line_no}.end")
        except Exception:
            return None

        for alias, entity_type, entity_key in self.get_entity_aliases():
            start = 0
            while True:
                pos = line_text.find(alias, start)
                if pos < 0:
                    break
                end = pos + len(alias)

                # 點在名稱本體時命中。
                if pos <= col_no < end:
                    return entity_type, entity_key, alias

                # 國家 LOG 常長成【國名】，容許點到緊貼名稱的全形括號。
                if pos > 0 and end < len(line_text):
                    if line_text[pos - 1] == "【" and line_text[end] == "】":
                        if pos - 1 <= col_no <= end:
                            return entity_type, entity_key, alias

                start = pos + max(1, len(alias))

        return None

    def on_entity_text_click(self, event):
        """所有文字區共用：點到哪個實體名稱，就精準跳到哪個詳細頁。"""
        widget = event.widget
        entity = self.entity_at_pointer(widget, event)
        if not entity:
            return

        entity_type, entity_key, _alias = entity
        if entity_type == "alliance":
            self.navigate_to_alliance(entity_key)
        else:
            self.navigate_to_country(entity_key)

        return "break"

    def on_entity_text_motion(self, event):
        """滑鼠移到可點擊國家／聯盟名稱時顯示手形游標。"""
        widget = event.widget
        try:
            widget.configure(cursor="hand2" if self.entity_at_pointer(widget, event) else "xterm")
        except Exception:
            pass

    def apply_entity_link_tags(self, widget):
        """掃描目前文字內容，替所有已知國家／聯盟名稱加上超連結外觀。"""
        try:
            widget.tag_remove("country_link", "1.0", tk.END)
            widget.tag_remove("alliance_link", "1.0", tk.END)

            for alias, entity_type, _entity_key in self.get_entity_aliases():
                if not alias:
                    continue

                start_pos = "1.0"
                tag_name = "alliance_link" if entity_type == "alliance" else "country_link"
                while True:
                    pos = widget.search(alias, start_pos, stopindex=tk.END)
                    if not pos:
                        break
                    end_pos = f"{pos}+{len(alias)}c"
                    widget.tag_add(tag_name, pos, end_pos)
                    start_pos = end_pos
        except tk.TclError:
            pass

    @staticmethod
    def _compact_text(value, limit=56):
        """表格用短文字，避免一格太長破壞版面。"""
        text = str(value if value is not None else "")
        return text if len(text) <= limit else text[: max(1, limit - 1)] + "…"

    @staticmethod
    def _replace_tree_rows(tree, rows):
        """整批更新 Treeview，不使用捲動文字區。"""
        for item in tree.get_children():
            tree.delete(item)
        for row in rows:
            tree.insert("", "end", values=row)

    @staticmethod
    def _war_tactic_name(value):
        mapping = {
            "BATTLE": "正面會戰",
            "SIEGE": "攻城戰",
            "RAID": "戰時掠奪",
            "宣戰": "宣戰",
            "尚未交鋒": "尚未交鋒",
        }
        return mapping.get(str(value), str(value))

    def _build_rank_map(self):
        alive = sorted(
            [
                (key, data)
                for key, data in self.raw_countries_data.items()
                if data.get("is_alive", True)
            ],
            key=lambda item: item[1].get("power", 0),
            reverse=True,
        )
        return {key: idx for idx, (key, _data) in enumerate(alive, start=1)}

    def on_country_war_double_click(self, event=None):
        """雙擊國家戰爭表的交戰對象，優先跳聯盟，否則跳國家。"""
        item = self.country_war_tree.focus()
        values = self.country_war_tree.item(item, "values") if item else ()
        if len(values) < 3:
            return
        enemy = str(values[2]).strip()
        if not enemy or enemy == "無":
            return
        if self.navigate_to_alliance(enemy):
            return
        self.navigate_to_country(enemy)

    def on_alliance_member_double_click(self, event=None):
        """雙擊聯盟成員列直接進入該國詳細查詢。"""
        item = self.alliance_member_tree.focus()
        values = self.alliance_member_tree.item(item, "values") if item else ()
        if values:
            self.navigate_to_country(str(values[0]))

    def on_alliance_war_double_click(self, event=None):
        """雙擊聯盟戰爭表的敵方名稱跳轉。"""
        item = self.alliance_war_tree.focus()
        values = self.alliance_war_tree.item(item, "values") if item else ()
        if len(values) < 3:
            return
        enemy = str(values[2]).strip()
        if not enemy or enemy == "無":
            return
        if self.navigate_to_alliance(enemy):
            return
        self.navigate_to_country(enemy)

    def on_header_click(self, tree, col):
        """點擊標題時反轉排序方向並記錄狀態"""
        if tree == self.tree_country:
            curr_col, curr_rev = self.country_sort_state
            new_rev = not curr_rev if curr_col == col else True
            self.country_sort_state = (col, new_rev)
            self.apply_sort(self.tree_country, col, new_rev)
        else:
            curr_col, curr_rev = self.alliance_sort_state
            new_rev = not curr_rev if curr_col == col else True
            self.alliance_sort_state = (col, new_rev)
            self.apply_sort(self.tree_alliance, col, new_rev)

    def apply_sort(self, tree, col, reverse):
        """執行列表排序與重新排列"""
        data_list = [(tree.set(k, col), k) for k in tree.get_children('')]
        if not data_list:
            return

        try:
            data_list.sort(key=lambda t: float(str(t[0]).replace(',', '')), reverse=reverse)
        except ValueError:
            data_list.sort(key=lambda t: str(t[0]), reverse=reverse)

        for index, (val, k) in enumerate(data_list):
            tree.move(k, '', index)

    def setup_rich_log_tags(self, target_widget):
        target_widget.tag_config("tag_war", foreground="#AAAAAA")
        target_widget.tag_config("tag_march", foreground="#569CD6")
        target_widget.tag_config("tag_destroy", foreground="#CE9178")
        target_widget.tag_config("tag_defeat", foreground="#FF5555", font=FONT_LOG_BOLD)
        target_widget.tag_config("tag_reject", foreground="#E51400", font=FONT_LOG_BOLD)
        target_widget.tag_config("tag_diplomacy", foreground="#DCDCAA")
        target_widget.tag_config("tag_global", foreground="#4EC9B0")

        target_widget.tag_config("number", foreground="#4FC1FF", font=FONT_LOG_BOLD)
        target_widget.tag_config("nation", foreground="#DCDCAA", font=FONT_LOG_BOLD)
        target_widget.tag_config("highlight", foreground="#D16969", font=FONT_LOG_BOLD)
        target_widget.tag_config("exclamation", foreground="#D7BA7D", font=FONT_LOG_BOLD)

    def filter_country_cb(self, event=None):
        typed_text = self.country_cb.get().strip().lower()
        all_countries = list(self.raw_countries_data.keys())

        if not typed_text:
            self.country_cb['values'] = all_countries
            return

        filtered = [
            k for k, v in self.raw_countries_data.items()
            if typed_text in k.lower() or typed_text in v.get("display_name", "").lower()
        ]
        
        self.country_cb['values'] = filtered
        if filtered:
            self.country_cb.set(filtered[0])
            self.on_country_selected()

    def filter_alliance_cb(self, event=None):
        typed_text = self.ally_cb.get().strip().lower()
        all_alliances = list(self.raw_alliances_data.keys())

        if not typed_text:
            self.ally_cb['values'] = all_alliances
            return

        filtered = [a for a in all_alliances if typed_text in a.lower()]
        self.ally_cb['values'] = filtered
        if filtered:
            self.ally_cb.set(filtered[0])
            self.on_alliance_selected()

    def append_rich_log_line_to_widget(self, target_widget, line):
        if not line.strip():
            return

        prefix_tag = None
        if any(tag in line for tag in (
            "[戰爭交鋒]", "[正式宣戰]", "[持續會戰]",
            "[攻城戰]", "[戰時掠奪]", "[戰爭結算]",
            "[戰爭結束]", "[戰敗求和]", "[國都陷落]",
            "[人口變動]"
        )):
            prefix_tag = "tag_war"
        elif "[出兵征戰]" in line:
            prefix_tag = "tag_march"
        elif "[戰爭拆屋]" in line:
            prefix_tag = "tag_destroy"
        elif "[擊破滅亡]" in line:
            prefix_tag = "tag_defeat"
        elif "[拒絕求和]" in line:
            prefix_tag = "tag_reject"
        elif "[外交策略]" in line:
            prefix_tag = "tag_diplomacy"
        elif "[全球事件]" in line:
            prefix_tag = "tag_global"

        pattern = re.compile(r'(【[^】]+】|\d+|[！!]|狠心拒絕|繼續血洗|願獻糧草求和)')
        tokens = pattern.split(line)

        for token in tokens:
            if not token:
                continue
            if token.startswith("【") and token.endswith("】"):
                target_widget.insert(tk.END, token, "nation")
            elif token.isdigit():
                target_widget.insert(tk.END, token, "number")
            elif token in ["！", "!"]:
                target_widget.insert(tk.END, token, "exclamation")
            elif token in ["狠心拒絕", "繼續血洗"]:
                target_widget.insert(tk.END, token, "highlight")
            else:
                target_widget.insert(tk.END, token, prefix_tag if prefix_tag else "")

        target_widget.insert(tk.END, "\n")

    def get_country_related_alliances(self, country_key):
        """取得與指定國家直接相關的聯盟。

        關聯定義：
        1. 國家目前的 current_alliance。
        2. 聯盟 members 中包含該國。
        3. 該聯盟的 target_hegemon 正是該國（例如反霸權討伐目標）。

        回傳聯盟名稱串列，供國家專屬 LOG 一併搜尋。
        """
        if not country_key or country_key not in self.raw_countries_data:
            return []

        country = self.raw_countries_data[country_key]
        display_name = country.get("display_name", country_key)
        related = set()

        current_alliance = country.get("current_alliance", "")
        if current_alliance and current_alliance in self.raw_alliances_data:
            related.add(current_alliance)

        for ally_name, details in self.raw_alliances_data.items():
            members = details.get("members", []) or []
            target = details.get("target_hegemon", "") or ""

            # 成員可能保存 country key，也可能保存 display_name，兩種都相容。
            if country_key in members or display_name in members:
                related.add(ally_name)

            # 圍剿目標同樣兼容 key / display_name。
            if target == country_key or target == display_name:
                related.add(ally_name)

        return sorted(related)

    def load_specific_logs(self, target_widget, search_terms, force_top=False):
        """載入專屬 LOG；內容沒變就不重畫，避免定時刷新造成視窗亂跳。

        search_terms 可傳單一字串或多個關聯詞。
        force_top=True 只在使用者主動切換國家／聯盟時使用。
        背景自動刷新時，即使 LOG 有新增，也盡量保留原本閱讀位置。
        """
        if isinstance(search_terms, str):
            terms = [search_terms] if search_terms else []
        else:
            terms = [str(t).strip() for t in (search_terms or []) if str(t).strip()]

        terms = list(dict.fromkeys(terms))

        matched_lines = []
        if os.path.exists(save_path("game.log")) and terms:
            try:
                with open(save_path("game.log"), "r", encoding="utf-8") as f:
                    seen = set()
                    for raw_line in f:
                        line = raw_line.strip()
                        if not line or line in seen:
                            continue
                        if any(term in line for term in terms):
                            matched_lines.append(line)
                            seen.add(line)
                            if len(matched_lines) >= MAX_SPECIFIC_LOG_LINES:
                                break
            except Exception:
                matched_lines = ["（無法讀取日誌檔案）"]
        elif terms:
            matched_lines = ["（無相關事件紀錄）"]

        if not matched_lines:
            matched_lines = ["（無相關事件紀錄）"]

        cache_key = str(target_widget)
        new_signature = tuple(matched_lines)
        old_signature = self._specific_log_cache.get(cache_key)

        # 背景刷新且內容完全相同：完全不碰 Text widget。
        if not force_top and old_signature == new_signature:
            return

        try:
            old_y = target_widget.yview()[0]
        except Exception:
            old_y = 0.0

        target_widget.config(state=tk.NORMAL)
        target_widget.delete("1.0", tk.END)

        for line in matched_lines:
            if line.startswith("（") and line.endswith("）"):
                target_widget.insert(tk.END, line + "\n")
            else:
                self.append_rich_log_line_to_widget(target_widget, line)

        self.apply_entity_link_tags(target_widget)
        self._specific_log_cache[cache_key] = new_signature

        if force_top:
            # 主動切換到另一個查詢對象：從最新事件開始看。
            target_widget.yview_moveto(0.0)
        else:
            # 背景更新：不搶使用者目前正在閱讀的位置。
            try:
                target_widget.yview_moveto(old_y)
            except Exception:
                pass

    def on_alliance_selected(self, event=None):
        selected_name = self.ally_cb.get()
        if not selected_name or selected_name not in self.raw_alliances_data:
            return

        alliance_changed = selected_name != self._last_alliance_log_owner
        self._last_alliance_log_owner = selected_name

        a = self.raw_alliances_data[selected_name]
        members = a.get("members", []) or []
        target = a.get("target_hegemon", "無") or "無"
        is_coalition = bool(a.get("is_coalition", False))
        entity_type_text = "臨時反霸權聯軍" if is_coalition else "普通聯盟"

        # ----- 聯盟摘要 -----
        active_war_count = 0
        member_key_set = set()
        for member in members:
            key = self.resolve_country_key(member)
            if key:
                member_key_set.add(key)

        for war in (self.raw_active_wars or {}).values():
            if not isinstance(war, dict):
                continue
            war_people = set(war.get("attacker_members", []) or []) | set(
                war.get("defender_members", []) or []
            )
            if member_key_set & war_people:
                active_war_count += 1

        summary_rows = [
            ("聯盟名稱", selected_name),
            ("聯盟類型", entity_type_text),
            ("總戰力", f"{a.get('total_power', 0):,}"),
            (
                "成員數量",
                f"{a.get('alive_member_count', 0)} / {a.get('member_count', 0)}（存活 / 總數）",
            ),
            (
                "目前狀態",
                f"⚔️ 參與 {active_war_count} 場戰爭"
                if active_war_count
                else "🟢 和平",
            ),
        ]
        if is_coalition:
            summary_rows.append(("討伐目標", target))
        else:
            last_war_vote = a.get("last_war_vote", {}) or {}
            last_join_vote = a.get("last_join_vote", {}) or {}

            council_votes = [
                vote
                for vote in (last_war_vote, last_join_vote)
                if isinstance(vote, dict) and vote
            ]

            if council_votes:
                last_vote = max(
                    council_votes,
                    key=lambda vote: int(vote.get("turn", 0) or 0),
                )
                vote_kind = str(last_vote.get("kind", "議會表決"))
                vote_result = str(last_vote.get("result", ""))

                if vote_kind == "進攻表決":
                    vote_target = str(
                        last_vote.get("target_name", "未知目標")
                    )
                    if "yes_weight" in last_vote:
                        vote_text = (
                            f"開戰{vote_result}｜{vote_target}｜"
                            f"戰力票 {int(last_vote.get('yes_weight', 0) or 0):,}/"
                            f"{int(last_vote.get('threshold_weight', last_vote.get('threshold', 0)) or 0):,}"
                        )
                    else:
                        vote_text = (
                            f"開戰{vote_result}｜{vote_target}｜"
                            f"{last_vote.get('yes', 0)}贊成/"
                            f"{last_vote.get('threshold', 0)}門檻"
                        )
                elif vote_kind == "入盟表決":
                    candidate_name = str(
                        last_vote.get("candidate_name", "未知申請國")
                    )
                    if "yes_weight" in last_vote:
                        vote_text = (
                            f"入盟{vote_result}｜{candidate_name}｜"
                            f"戰力票 {int(last_vote.get('yes_weight', 0) or 0):,}/"
                            f"{int(last_vote.get('threshold_weight', last_vote.get('threshold', 0)) or 0):,}"
                        )
                    else:
                        vote_text = (
                            f"入盟{vote_result}｜{candidate_name}｜"
                            f"{last_vote.get('yes', 0)}贊成/"
                            f"{last_vote.get('threshold', 0)}門檻"
                        )
                else:
                    vote_target = str(
                        last_vote.get("target_name", "未知目標")
                    )
                    vote_text = (
                        f"{vote_kind}｜{vote_result}｜{vote_target}"
                    )

                summary_rows.append(
                    (
                        "最近議會表決",
                        self._compact_text(vote_text, 44),
                    )
                )

        self._replace_tree_rows(self.alliance_summary_tree, summary_rows)

        # ----- 聯盟成員明細 -----
        rank_map = self._build_rank_map()
        member_rows = []
        member_data = []

        for member in members:
            key = self.resolve_country_key(member)
            if not key or key not in self.raw_countries_data:
                member_data.append(
                    (member, 999999999, ("未知", "-", "-", "-", "-", "未知"))
                )
                continue

            c = self.raw_countries_data[key]
            display_name = c.get("display_name", key)
            rank = rank_map.get(key)
            row = (
                display_name,
                f"第 {rank} 名" if rank else "-",
                f"{c.get('power', 0):,}",
                f"{c.get('pop_total', 0):,}",
                f"{c.get('soldiers', 0):,}",
                (
                    "滅亡"
                    if not c.get("is_alive", True)
                    else ("戰中" if c.get("current_wars") else "存活")
                ),
            )
            member_data.append((display_name, c.get("power", 0), row))

        member_data.sort(key=lambda x: x[1], reverse=True)

        # 完整列出所有聯盟成員；表格固定顯示約 6 列，
        # 成員更多時直接用右側捲軸查看，不再顯示「另有 X 國」。
        member_rows = [
            row for _name, _power, row in member_data
        ]

        if not member_rows:
            member_rows = [("無成員", "-", "-", "-", "-", "-")]

        self._replace_tree_rows(
            self.alliance_member_tree,
            member_rows,
        )

        # ----- 聯盟當前戰爭 -----
        war_rows = []
        war_log_terms = [selected_name]

        for war_id, war in (self.raw_active_wars or {}).items():
            if not isinstance(war, dict):
                continue

            att_members = set(war.get("attacker_members", []) or [])
            def_members = set(war.get("defender_members", []) or [])
            is_attacker = bool(member_key_set & att_members)
            is_defender = bool(member_key_set & def_members)

            if not is_attacker and not is_defender:
                continue

            enemy = (
                str(war.get("defender_name", "防守方"))
                if is_attacker
                else str(war.get("attacker_name", "進攻方"))
            )
            role = "進攻方" if is_attacker else "防守方"
            rounds = int(war.get("rounds", 0) or 0)
            planned = int(war.get("planned_duration", 0) or 0)
            round_text = f"{rounds}/{planned}" if planned > 0 else str(rounds)
            tactic = self._war_tactic_name(
                war.get("last_tactic", "尚未交鋒")
            )

            war_rows.append(
                (str(war_id), role, enemy, round_text, tactic)
            )
            war_log_terms.extend([str(war_id), enemy])

        if not war_rows:
            war_rows = [("-", "和平", "無", "-", "-")]

        self._replace_tree_rows(
            self.alliance_war_tree,
            war_rows,
        )

        # LOG 也納入戰爭編號 / 敵方名稱，聯盟戰報比較完整。
        self.load_specific_logs(
            self.ally_log_text,
            list(dict.fromkeys(war_log_terms)),
            force_top=alliance_changed,
        )

    def get_country_current_rank(self, country_key):
        """依目前存活國家的綜合戰力取得即時排名。"""
        if not country_key or country_key not in self.raw_countries_data:
            return "無資料"

        country = self.raw_countries_data[country_key]
        if not country.get("is_alive", True):
            return "已滅亡（不列入存活排名）"

        alive_sorted = sorted(
            [
                (key, data)
                for key, data in self.raw_countries_data.items()
                if data.get("is_alive", True)
            ],
            key=lambda item: item[1].get("power", 0),
            reverse=True,
        )

        for idx, (key, _data) in enumerate(alive_sorted, start=1):
            if key == country_key:
                return f"第 {idx} 名 / 存活 {len(alive_sorted)} 國"

        return "無資料"

    def get_country_war_details(self, country_key):
        """整理國家目前參與中的正式戰爭資料。"""
        result = {
            "is_at_war": False,
            "offense": [],
            "defense": [],
            "lines": [],
            "rows": [],
            "log_terms": [],
        }

        if not country_key or country_key not in self.raw_countries_data:
            return result

        country = self.raw_countries_data[country_key]
        display_name = country.get("display_name", country_key)

        for war_id, war in (self.raw_active_wars or {}).items():
            if not isinstance(war, dict):
                continue

            attacker_members = war.get("attacker_members", []) or []
            defender_members = war.get("defender_members", []) or []

            is_attacker = (
                country_key in attacker_members
                or display_name in attacker_members
            )
            is_defender = (
                country_key in defender_members
                or display_name in defender_members
            )

            if not is_attacker and not is_defender:
                continue

            attacker_name = str(war.get("attacker_name", "進攻方"))
            defender_name = str(war.get("defender_name", "防守方"))
            rounds = int(war.get("rounds", 0) or 0)
            planned = int(war.get("planned_duration", 0) or 0)
            last_tactic = str(
                war.get("last_tactic", "尚未交鋒") or "尚未交鋒"
            )

            result["is_at_war"] = True
            result["log_terms"].extend(
                [str(war_id), attacker_name, defender_name]
            )

            if is_attacker:
                result["offense"].append(defender_name)
                role_text = "⚔️ 進攻方"
                relation_text = "主動宣戰"
                enemy_name = defender_name
            else:
                result["defense"].append(attacker_name)
                role_text = "🛡️ 防守方"
                relation_text = "遭到宣戰"
                enemy_name = attacker_name

            round_text = f"{rounds}/{planned}" if planned > 0 else str(rounds)

            result["lines"].append(
                f"• {war_id}｜{role_text}｜{relation_text}：【{enemy_name}】"
                f"｜戰爭回合：{round_text}｜最近戰術：{last_tactic}"
            )
            participant_wars = []
            for _wid, _war in (self.raw_active_wars or {}).items():
                if not isinstance(_war, dict):
                    continue
                _participants = set(_war.get("attacker_members", []) or []) | set(
                    _war.get("defender_members", []) or []
                )
                if country_key in _participants or display_name in _participants:
                    participant_wars.append(
                        (int(_war.get("started_turn", 0) or 0), str(_wid))
                    )
            participant_wars.sort(key=lambda x: (x[0], x[1]))
            ordered_ids = [wid for _turn, wid in participant_wars]
            try:
                front_no = ordered_ids.index(str(war_id)) + 1
            except ValueError:
                front_no = 1

            role_value = "進攻方" if is_attacker else "防守方"
            if front_no >= 2:
                role_value += "・第二線"

            result["rows"].append(
                (
                    str(war_id),
                    role_value,
                    enemy_name,
                    round_text,
                    self._war_tactic_name(last_tactic),
                )
            )

        result["offense"] = list(dict.fromkeys(result["offense"]))
        result["defense"] = list(dict.fromkeys(result["defense"]))
        result["log_terms"] = list(dict.fromkeys(result["log_terms"]))
        return result

    @staticmethod
    def _chronicle_year_text(value):
        if value in (None, ""):
            return "—"
        try:
            year = int(value)
        except (TypeError, ValueError):
            return str(value)
        if year <= 0:
            return "舊檔未知"
        return f"{year:,}年"

    def on_chronicle_country_selected(self, event=None):
        """更新右側「國家編年史」表格。"""
        selected = self.chronicle_country_cb.get().strip()
        country_key = self.resolve_country_key(selected)

        if not country_key or country_key not in self.raw_countries_data:
            return

        # 下拉框統一保留國家內部 key，避免 display_name 改名後失去對應。
        if self.chronicle_country_cb.get() != country_key:
            self.chronicle_country_cb.set(country_key)

        c = self.raw_countries_data[country_key]
        history = list(c.get("country_chronicle", []) or [])

        rows = []
        current_year = max(1, int(self.raw_turn_counter or 1))

        for item in history:
            if not isinstance(item, dict):
                continue

            generation = int(item.get("generation", 1) or 1)
            name = str(item.get("name", country_key) or country_key)
            regime_type = str(item.get("regime_type", "正統政權") or "正統政權")

            # personality = str(item.get("personality") or "紀錄遺失")

            start_year = item.get("start_year")
            end_year = item.get("end_year")

            if end_year in (None, ""):
                if start_year not in (None, "") and int(start_year or 0) > 0:
                    duration_years = max(
                        1,
                        current_year - int(start_year) + 1,
                    )
                else:
                    duration_years = None
                end_text = "現行"
                reason_text = "現行世代"
                tag = "current"
            else:
                duration_years = item.get("duration_years")
                if duration_years in (None, ""):
                    sy = int(start_year or 0)
                    ey = int(end_year or 0)
                    duration_years = (
                        max(1, ey - sy + 1)
                        if sy > 0 and ey > 0
                        else None
                    )
                end_text = self._chronicle_year_text(end_year)

                reason = str(item.get("end_reason", "") or "")
                ended_by = str(item.get("ended_by", "") or "")
                if reason == "滅國" and ended_by:
                    reason_text = f"|{ended_by}|"
                elif ended_by:
                    reason_text = f"{reason}（{ended_by}）"
                else:
                    reason_text = reason or "—"
                tag = ""

            peak_power = int(item.get("peak_power", 0) or 0)
            peak_power_year = item.get("peak_power_year")
            if peak_power > 0:
                if peak_power_year not in (None, "") and int(peak_power_year or 0) > 0:
                    peak_power_text = (
                        f"{peak_power:,}（{int(peak_power_year):,}年）"
                    )
                else:
                    peak_power_text = f"{peak_power:,}"
            else:
                peak_power_text = "—"

            peak_population = int(item.get("peak_population", 0) or 0)
            peak_population_text = (
                f"{peak_population:,}"
                if peak_population > 0
                else "—"
            )

            best_rank = item.get("best_rank")
            best_rank_text = (
                f"第 {int(best_rank)} 名"
                if best_rank not in (None, "", 0)
                else "—"
            )

            rows.append(
                (
                    generation,
                    name,
                    regime_type,
                    # personality,
                    self._chronicle_year_text(start_year),
                    end_text,
                    (
                        f"{int(duration_years):,}年"
                        if duration_years not in (None, "")
                        else "—"
                    ),
                    reason_text,
                    peak_power_text,
                    peak_population_text,
                    best_rank_text,
                    tag,
                )
            )

        signature = (
            country_key,
            current_year,
            tuple(tuple(row[:-1]) for row in rows),
        )

        if signature != self._chronicle_signature:
            self._chronicle_signature = signature
            for iid in self.chronicle_tree.get_children():
                self.chronicle_tree.delete(iid)

            for row in rows:
                values = row[:-1]
                tag = row[-1]
                self.chronicle_tree.insert(
                    "",
                    "end",
                    values=values,
                    tags=(tag,) if tag else (),
                )

            # 最新世代保持可見。
            children = self.chronicle_tree.get_children()
            if children:
                self.chronicle_tree.see(children[-1])

        current_gen = int(
            c.get(
                "country_generation",
                c.get("gen", 1),
            )
            or 1
        )
        current_name = c.get("display_name", country_key)
        tenure = int(c.get("regime_tenure", 0) or 0)

        self.chronicle_year_label.configure(
            text=f"世界曆：第 {current_year:,} 年"
        )
        self.chronicle_summary_label.configure(
            text=(
                f"目前：{current_name}｜國家第 {current_gen} 世代｜"
                f"{c.get('regime_type', '正統政權')}｜"
                f"本政權存續 {tenure:,} 年｜"
                f"編年史 {len(history)} 筆"
            )
        )


    def open_selected_country_experience(self):
        """依詳細查詢目前選中的國家顯示其戰略 Q 報表。"""
        country_key = self.resolve_country_key(self.country_cb.get().strip())
        if not country_key or country_key not in self.raw_countries_data:
            return
        self.experience_country_key = country_key
        self.refresh_country_experience()
        self.left_notebook.select(self.tab_detail)
        self.experience_page.tkraise()

    def refresh_country_experience(self):
        country_key = self.experience_country_key
        if not country_key:
            return
        country = self.raw_countries_data.get(country_key, {})
        display_name = str(country.get("display_name", country_key))
        self.experience_title.configure(text=f"{display_name}｜戰略 Q 值")
        q_path = save_path("rl_agents_q_tables.json")
        try:
            with open(q_path, "r", encoding="utf-8-sig") as handle:
                agents = json.load(handle)
            state = current_strategic_state(country_key, self.raw_countries_data)
            content = render_current_q(display_name, state, agents.get(country_key), STRATEGIC_ACTIONS)
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            content = f"目前無法讀取經驗資料：{exc}\n報表位置：{q_path}"
        self.experience_text.configure(state="normal")
        self.experience_text.delete("1.0", "end")
        self.experience_text.insert("1.0", content)
        self.experience_text.configure(state="disabled")
        self.experience_text.yview_moveto(0)

    def return_from_country_experience(self):
        if self.experience_country_key in self.raw_countries_data:
            self.country_cb.set(self.experience_country_key)
            self.on_country_selected()
        self.country_detail_page.tkraise()
        self.left_notebook.select(self.tab_detail)

    def open_selected_country_chronicle(self):
        """
        左側國家詳細資訊 → 左側國家編年史。
        保留使用者指定的「📜 編年史」按鈕位置。
        """
        selected = self.country_cb.get().strip()
        country_key = self.resolve_country_key(selected)

        if (
            not country_key
            or country_key not in self.raw_countries_data
        ):
            return

        self.chronicle_country_cb.set(country_key)
        self.on_chronicle_country_selected()

        # 同一個左側 Tab 內切換內容。
        self.left_notebook.select(self.tab_detail)
        self.chronicle_page.tkraise()
        self.chronicle_tree.focus_set()


    def return_to_country_detail(self):
        """
        左側國家編年史 → 左側國家詳細資訊。
        保持同一個國家，不改變右半側即時戰局。
        """
        selected = self.chronicle_country_cb.get().strip()
        country_key = self.resolve_country_key(selected)

        if (
            country_key
            and country_key in self.raw_countries_data
        ):
            self.country_cb.set(country_key)
            self.on_country_selected()

        self.country_detail_page.tkraise()
        self.left_notebook.select(self.tab_detail)


    def on_country_selected(self, event=None):
        selected_name = self.country_cb.get()
        if not selected_name or selected_name not in self.raw_countries_data:
            return

        country_changed = selected_name != self._last_country_log_owner
        self._last_country_log_owner = selected_name

        c = self.raw_countries_data[selected_name]
        international_dread = max(0, int(c.get("international_dread", 0) or 0))
        championship_records = list(
            c.get("championship_records", []) or []
        )

        current_rank = self.get_country_current_rank(selected_name)
        war_info = self.get_country_war_details(selected_name)

        # ----- 基本狀態 -----
        basic_rows = [
            (
                "國家狀態",
                (
                    ("🟢 存活" if c.get("is_alive", True) else "🔴 滅亡")
                    + f"｜{c.get('display_name', selected_name)}"
                ),
            ),
            ("目前排名", current_rank),
            ("綜合戰力", f"{c.get('power', 0):,}"),
            (
                "國家世代 / 政權",
                (
                    f"第 {c.get('country_generation', c.get('gen', 1))} 世代"
                    f"｜{c.get('regime_type', '正統政權')}"
                    f"・第 {c.get('regime_generation', 1)} 世"
                    # f"｜存續 {int(c.get('regime_tenure', 0) or 0):,} 年"
                ),
            ),
            (
                "戰略 / 世界",
                (
                    f"{c.get('strategic_mode', '正常發展')}"
                    f"｜{self.raw_world_mode.get('name', '平常局勢')}"
                    f"｜{c.get('season_phase_name', '本屆前段')}"
                ),
            ),
            ("國家個性", c.get("ai_personality", "尚在形成中")),
            (
                "財力 / 當前缺口",
                f"{c.get('cash_status', '尚未評估')}｜"
                f"優先需求 {c.get('market_need_resource', '尚未評估')}",
            ),          
            (
                "聯盟履歷",
                f"嘗試 {int(c.get('alliance_attempts', 0) or 0)}｜"
                f"成功 {int(c.get('alliance_successes', 0) or 0)}｜"
                f"遭拒 {int(c.get('alliance_rejections', 0) or 0)}｜"
                f"瓦解 {int(c.get('alliance_dissolutions', 0) or 0)}",
            ),
            ("最近聯盟結果", c.get("alliance_last_result", "尚未嘗試")),
            (
                "最近戰爭評估",
                f"{c.get('last_war_target', '尚未評估')}｜"
                f"{c.get('last_war_assessment', '尚未評估')}｜"
                f"撤回 {int(c.get('war_assessment_cancellations', 0) or 0)} 次",
            ),
            ("防禦工事", f"{c.get('fortification', 0)} / 100"),
            (
                "惡名 / 探索",
                f"{c.get('infamy', 0)}｜"
                f"{float(c.get('ai_epsilon', 0.0) or 0.0):.3f}",
            ),
            (
                "AI 決策 / 延遲獎勵",
                f"{int(c.get('ai_decision_count', 0) or 0):,} 次｜"
                f"{float(c.get('last_delayed_reward', 0.0) or 0.0):+.2f}",
            ),
            (
                "多層策略 / TD 誤差",
                f"戰略 {int(c.get('q_state_count', 0) or 0):,}｜"
                f"市場 {int(c.get('market_q_state_count', 0) or 0):,}｜"
                f"聯盟 {int(c.get('alliance_q_state_count', 0) or 0):,}｜"
                f"{float(c.get('strategic_td_error', 0.0) or 0.0):.3f}",
            ),
            (
                "市場 / 聯盟子策略",
                f"{c.get('last_market_policy', '尚未決策')} "
                f"({float(c.get('last_market_reward', 0.0) or 0.0):+.2f})｜"
                f"{c.get('last_alliance_policy', '尚未決策')} "
                f"({float(c.get('last_alliance_reward', 0.0) or 0.0):+.2f})",
            ),
        ]
        self._replace_tree_rows(self.country_basic_tree, basic_rows)

        # ----- 人口、建築與資源 -----
        pop_total = max(0, int(c.get("pop_total", 0) or 0))
        soldiers = max(0, int(c.get("soldiers", 0) or 0))
        military_ratio = soldiers / max(1, pop_total) * 100

        econ_rows = [
            (
                "房屋 / 基礎建設",
                f"{c.get('houses', 0):,} 間 (容納 {c.get('houses', 0) * 10:,} 人)｜"
                f" {int(c.get('infrastructure', 0) or 0)} %",
            ),        
            (
                "穩定 / 疲勞",
                f"{float(c.get('political_stability', 75) or 75):.0f}/100 ｜ "
                f"{float(c.get('war_exhaustion', 0) or 0):.0f}/100",
            ),
            ("人口 / 政策", f"{pop_total:,} 人 / {c.get('policy_summary', '無')}"),
            ("農夫 / 士兵", f"{c.get('farmers', 0):,} 人 / {soldiers:,} 人（{military_ratio:.1f}%）"),

            (
                "產業配置",
                f"{c.get('industry_focus_name', '自動配置')}｜"
                f"剩 {int(c.get('industry_focus_turns', 0) or 0)} 年",
            ),
            (f"糧食 / {self.raw_world_bank.get('currency', '大洋')}", f"{c.get('food', 0):,} / {c.get('gold', 0):,}"),
            ("木材 / 礦產", f"{c.get('wood', 0):,} / {c.get('metal', 0):,}"),
        ]
        self._replace_tree_rows(self.country_econ_tree, econ_rows)

        # ----- 當前正式戰爭 -----
        war_rows = war_info.get("rows", [])
        if not war_rows:
            war_rows = [("-", "和平", "無", "-", "-")]
        self._replace_tree_rows(self.country_war_tree, war_rows[:2])

        war_count = len(war_info.get("rows", []))
        self.country_war_group.configure(
            text=(
                f" ⚔️ 當前戰爭｜{war_count} 場 "
                if war_count
                else " ⚔️ 當前戰爭｜和平 "
            )
        )

        # ----- 外交與戰績 -----
        record_rows = [
            (
                "普通聯盟",
                c.get("current_alliance") or "無聯盟（單打獨鬥）",
            ),
            (
                "反霸權聯軍",
                c.get("current_coalition") or "未參與",
            ),
            (
                "歷史參戰",
                (
                    f"{c.get('wars_fought', 0)} 場｜"
                    f"勝 {c.get('wars_won', 0)}／敗 {c.get('wars_lost', 0)}／和 {c.get('wars_drawn', 0)}"
                    + (f"／戰中 {len(c.get('current_wars', []) or [])}" if c.get("current_wars") else "")
                ),
            ),
            (
                "征服戰績",
                f"攻陷國都 {c.get('capital_captures', 0)} 次｜吞併 {c.get('annexed_count', 0)} 國",
            ),
            (
                "最高仇恨",
                self._compact_text(c.get("top_hostility_target", "無"), 44),
            ),
            (
                "近期事件",
                self._compact_text(c.get("last_event", "無"), 48),
            ),
            (
                "國際忌憚值",
                f"{international_dread:,}",
            ),
        ]
        self._replace_tree_rows(self.country_record_tree, record_rows)

        # ----- 完整奪冠紀錄 -----
        # 右側獨立表格完整保存所有冠軍紀錄；最新一次顯示在最上方。
        champion_rows = []
        for idx, record in enumerate(
            reversed(championship_records),
            start=1,
        ):
            original_no = len(championship_records) - idx + 1
            record_text = str(record)
            match = re.match(r"R(\d+)__(\d+)__(.+)", record_text)
            if match:
                record_text = (
                    f"第 {match.group(1)} 屆｜戰力 {int(match.group(2)):,}｜{match.group(3)}"
                )
            champion_rows.append(
                (
                    f"第 {original_no} 次",
                    record_text,
                )
            )

        if not champion_rows:
            champion_rows = [("-", "尚無奪冠紀錄")]

        self._replace_tree_rows(
            self.country_champion_tree,
            champion_rows,
        )

        self.country_champion_group.configure(
            text=(
                f" 👑 完整奪冠紀錄｜共 {len(championship_records)} 次 "
            )
        )

        # 切換國家時，冠軍紀錄自動回到最上方（最新紀錄）。
        if country_changed:
            self.country_champion_tree.yview_moveto(0.0)

        # 人口稽核仍保留在引擎與 LOG 中，但不再塞進區塊標題，
        # 避免標題過長、壓縮表格寬度。
        self.country_econ_group.configure(
            text=" 👥 人口・建築・資源 "
        )

        # 國家專屬 LOG：國名 + 所屬聯盟 + 正式戰爭編號與敵方。
        related_alliances = self.get_country_related_alliances(selected_name)
        country_log_terms = (
            [selected_name, c.get("display_name", selected_name)]
            + related_alliances
            + war_info.get("log_terms", [])
        )
        self.load_specific_logs(
            self.country_log_text,
            country_log_terms,
            force_top=country_changed,
        )

    def toggle_pause(self):
        paused = toggle_simulation_paused()
        self.pause_button.configure(text="▶ 繼續" if paused else "⏸ 暫停")

    def on_speed_changed(self, event=None):
        value = self.speed_cb.get().replace(" 秒", "")
        try:
            set_simulation_speed(float(value))
        except ValueError:
            pass

    def refresh_world_market_panel(self):
        bank = self.raw_world_bank or {}
        market = self.raw_world_market or {}
        currency = bank.get("currency", "大洋")
        self.tree_country.heading("gold", text=currency)
        self.market_order_tree.heading("price", text=f"單價({currency})")
        circulating = sum(
            max(0, int(d.get("gold", 0) or 0))
            for d in self.raw_countries_data.values()
            if d.get("is_alive", True)
        )
        self.market_bank_label.configure(
            text=(
                f"🏦 世界銀行｜貨幣：{bank.get('currency', '大洋')}｜"
                f"發行倍率 {float(bank.get('policy_price_index', 1.0) or 1.0):.3f}｜"
                f"換幣面額 ×{int(bank.get('currency_denomination', 1) or 1):,}｜"
                f"生育費 {int(bank.get('birth_policy_cost', 120000) or 120000):,}｜"
                f"\n初始發行 {int(bank.get('initial_issued_total', 0) or 0):,}｜"
                f"累計發行 {int(bank.get('issued_total', 0) or 0):,}｜"
                f"銀行庫存 {int(bank.get('treasury', 0) or 0):,}｜"
                f"存活國流通 {circulating:,}｜"
                # f"已回流 {int(bank.get('liquidity_redistributed', 0) or 0):,}｜"
                f"守恆差額 {int(bank.get('currency_audit_gap', 0) or 0):+,}"
                # f"Seed {self.raw_world_bank.get('simulation_seed', '—')}"
            )
        )
        placed = max(0, int(market.get("orders_placed", 0) or 0))
        filled = max(0, int(market.get("orders_filled", 0) or 0))
        expired = max(0, int(market.get("orders_expired", 0) or 0))
        fill_rate = (filled / placed * 100.0) if placed else 0.0
        monitor = (market.get("price_monitor") or {}).get("latest", {}) or {}
        index_value = monitor.get("index")
        index_text = (f"{float(index_value):.4f}" if index_value is not None
                      else "樣本不足")
        price_turn = monitor.get("turn", "—")
        volume = int(monitor.get("volume", 0) or 0)
        spread = monitor.get("spread")
        spread_text = f"{float(spread) * 100:.1f}%" if spread is not None else "無雙邊報價"
        cash_pct = 100.0 * float(monitor.get("cash_stressed", 0) or 0)
        diagnosis = monitor.get("diagnosis", "尚待 10 年成交樣本")
        self.market_stats_label.configure(
            text=(f"市場品質｜累計掛單 {placed:,}｜完整成交 {filled:,}｜到期 {expired:,}｜成交率 {fill_rate:.1f}%"
                  f"\n實際成交物價指數 {index_text}（第 {price_turn} 年）｜10年成交量 {volume:,}｜"
                  f"平均報價價差 {spread_text}｜現金不足國 {cash_pct:.0f}%"
                  f"\n診斷：{diagnosis}｜穩定政策本屆增發 "
                  f"{int(bank.get('stabilization_issued_this_season', 0) or 0):,} {currency}"
                  f"｜累計增發 {int(bank.get('stabilization_issued_total', 0) or 0):,}")
        )

        stats = market.get("stats", {}) or {}
        quote_rows = []
        for res, name in (("food", "糧食"), ("wood", "木材"), ("metal", "金屬")):
            s = stats.get(res, {}) or {}
            last = float(s.get("last_price", 0.0) or 0.0)
            bid = s.get("best_bid")
            ask = s.get("best_ask")
            spread = (float(ask) - float(bid)) if bid not in (None, "") and ask not in (None, "") else None
            quote_rows.append((
                name,
                f"{last:.2f}",
                f"{float(s.get('vwap_10', last) or last):.2f}",
                f"{float(bid):.2f}" if bid not in (None, "") else "—",
                f"{float(ask):.2f}" if ask not in (None, "") else "—",
                f"{spread:.2f}" if spread is not None else "—",
                f"{int(s.get('buy_qty', 0) or 0):,}",
                f"{int(s.get('sell_qty', 0) or 0):,}",
                f"{int(s.get('traded_volume', 0) or 0):,}",
            ))
        self._replace_tree_rows(self.market_quote_tree, quote_rows)

        orders = list(market.get("orders", []) or [])
        orders.sort(key=lambda o: (int(o.get("turn", 0) or 0), int(str(o.get("id", "M0")).lstrip("M") or 0)), reverse=True)
        order_rows = []
        for o in orders[:40]:
            order_rows.append((
                "買" if o.get("side") == "BUY" else "賣",
                o.get("country_name", o.get("country", "")),
                o.get("resource_name", o.get("resource", "")),
                f"{int(o.get('qty', 0) or 0):,}",
                f"{float(o.get('price', 0.0) or 0.0):.2f}",
                o.get("turn", "—"),
            ))
        self._replace_tree_rows(self.market_order_tree, order_rows)

        trades = list(market.get("recent_trades", []) or [])
        trade_rows = []
        for t in reversed(trades[-20:]):
            trade_rows.append((
                t.get("turn", "—"),
                t.get("resource_name", t.get("resource", "")),
                f"{int(t.get('qty', 0) or 0):,}",
                f"{float(t.get('price', 0.0) or 0.0):.2f}",
                t.get("buyer_name", t.get("buyer", "")),
                t.get("seller_name", t.get("seller", "")),
            ))
        self._replace_tree_rows(self.market_trade_tree, trade_rows)

    def update_ui_data(self):
        """核心數據刷新：只在資料真的變動時重建大型表格，降低 UI 閃爍與 CPU 使用。"""
        try:
            # 1. 國家資料
            if os.path.exists(save_path("war_live_countries.json")):
                with open(save_path("war_live_countries.json"), "r", encoding="utf-8") as f:
                    c_json = json.load(f)

                new_countries = c_json.get("countries", {}) or {}
                self.raw_countries_data = new_countries
                self.raw_world_mode = c_json.get(
                    "world_mode",
                    self.raw_world_mode,
                ) or self.raw_world_mode
                self.raw_world_bank = c_json.get("world_bank", self.raw_world_bank) or self.raw_world_bank
                self.raw_world_market = c_json.get("world_market", self.raw_world_market) or self.raw_world_market
                self.engine_version = c_json.get("engine_version", "") or ""
                self.raw_turn_counter = int(
                    c_json.get("turn_counter", 0) or 0
                )
                if self.engine_version:
                    expected_title = f"{WINDOW_TITLE}｜{self.engine_version}"
                    if self.root.title() != expected_title:
                        self.root.title(expected_title)

                country_names = tuple(self.raw_countries_data.keys())
                if tuple(self.country_cb["values"]) != country_names:
                    self.country_cb["values"] = country_names
                if tuple(self.chronicle_country_cb["values"]) != country_names:
                    self.chronicle_country_cb["values"] = country_names

                if (
                    not self.chronicle_country_cb.get().strip()
                    and country_names
                ):
                    preferred = self.country_cb.get().strip()
                    self.chronicle_country_cb.set(
                        preferred
                        if preferred in self.raw_countries_data
                        else country_names[0]
                    )

                country_rows = []
                for key, data in self.raw_countries_data.items():
                    disp_name = data.get("display_name", key)
                    gen = data.get(
                        "country_generation",
                        data.get("gen", 1),
                    )
                    pwr = data.get("power", 0)
                    pop = data.get("pop_total", 0)
                    soldiers = data.get("soldiers", 0)
                    gold = data.get("gold", 0)
                    food = data.get("food", 0)
                    cham = data.get("championship_count", 0)
                    if not data.get("is_alive", True):
                        status = "滅亡"
                    elif data.get("current_wars"):
                        status = "戰中"
                    elif float(data.get("political_stability", 75) or 75) < 20:
                        status = "政危"
                    else:
                        status = "存活"
                    country_rows.append(
                        # (disp_name, gen, pwr, pop, soldiers, cham, status)
                        (disp_name, gen, pwr, pop, gold, cham, status)
                    )

                country_signature = tuple(country_rows)
                if country_signature != self._country_table_signature:
                    self._country_table_signature = country_signature
                    for item in self.tree_country.get_children():
                        self.tree_country.delete(item)
                    for row in country_rows:
                        self.tree_country.insert("", "end", values=row)
                    col, rev = self.country_sort_state
                    self.apply_sort(self.tree_country, col, rev)

            # 2. 聯盟 / 戰爭資料
            if os.path.exists(save_path("war_live_alliances.json")):
                with open(save_path("war_live_alliances.json"), "r", encoding="utf-8") as f:
                    a_json = json.load(f)

                self.raw_alliances_data = a_json.get("alliance_details", {}) or {}
                self.raw_active_wars = a_json.get("active_wars", {}) or {}

                alliance_names = tuple(self.raw_alliances_data.keys())
                if tuple(self.ally_cb["values"]) != alliance_names:
                    self.ally_cb["values"] = alliance_names

                alliance_rows = []
                for ally_name, details in self.raw_alliances_data.items():
                    pwr = details.get("total_power", 0)
                    m_count = (
                        f"{details.get('alive_member_count', 0)}/"
                        f"{details.get('member_count', 0)}"
                    )
                    target = details.get("target_hegemon", "無") or "無"
                    alliance_rows.append((ally_name, pwr, m_count, target))

                alliance_signature = tuple(alliance_rows)
                if alliance_signature != self._alliance_table_signature:
                    self._alliance_table_signature = alliance_signature
                    for item in self.tree_alliance.get_children():
                        self.tree_alliance.delete(item)
                    for row in alliance_rows:
                        self.tree_alliance.insert("", "end", values=row)
                    col, rev = self.alliance_sort_state
                    self.apply_sort(self.tree_alliance, col, rev)

            # 3. 世界銀行 / 世界報價系統
            self.refresh_world_market_panel()

            # 4. 排名：內容有變才重畫
            mode_name = str(
                self.raw_world_mode.get("name", "平常局勢")
            )
            mode_remaining = int(
                self.raw_world_mode.get("remaining_turns", 0) or 0
            )
            if self.raw_world_mode.get("code") != "NORMAL":
                self.rank_group.configure(
                    text=(
                        f" 🏆 世界即時排名｜🌍 {mode_name}"
                        f"（約剩 {mode_remaining} 回合） "
                    )
                )
            else:
                self.rank_group.configure(
                    text=" 🏆 世界即時排名｜🌍 平常局勢 "
                )

            if os.path.exists(save_path("Live_Ranking.txt")):
                with open(save_path("Live_Ranking.txt"), "r", encoding="utf-8") as f:
                    content = f.read()

                self.rank_text.tag_config(
                    "alliance_yellow",
                    foreground=COLOR_FG_YELLOW,
                    font=(FONT_FAMILY_MONO, FONT_SIZE_RANK, "bold"),
                )

                if self.rank_text.get("1.0", tk.END).strip() != content.strip():
                    self.rank_text.config(state=tk.NORMAL)
                    self.rank_text.delete("1.0", tk.END)
                    self.rank_text.insert(tk.END, content)

                    for ally_name in self.raw_alliances_data.keys():
                        if not ally_name:
                            continue
                        start_pos = "1.0"
                        while True:
                            pos = self.rank_text.search(
                                ally_name, start_pos, stopindex=tk.END
                            )
                            if not pos:
                                break
                            end_pos = f"{pos}+{len(ally_name)}c"
                            self.rank_text.tag_add(
                                "alliance_yellow", pos, end_pos
                            )
                            start_pos = end_pos

                    self.apply_entity_link_tags(self.rank_text)

            # 4. 全域 LOG：前 25 行沒有變就完全不重畫
            if os.path.exists(save_path("game.log")):
                with open(save_path("game.log"), "r", encoding="utf-8") as f:
                    lines = tuple(f.readlines()[:MAX_GLOBAL_LOG_LINES])

                if lines != self._global_log_cache:
                    self._global_log_cache = lines
                    self.log_text.config(state=tk.NORMAL)
                    self.log_text.delete("1.0", tk.END)
                    for line in lines:
                        self.append_rich_log_line_to_widget(
                            self.log_text, line.strip()
                        )
                    self.apply_entity_link_tags(self.log_text)
                    self.log_text.see("1.0")

            # 5. 當前選中頁面仍即時更新；資料量很小，不必做過度快取。
            current_country = self.country_cb.get().strip()
            if current_country and current_country in self.raw_countries_data:
                self.on_country_selected()

            current_ally = self.ally_cb.get().strip()
            if current_ally and current_ally in self.raw_alliances_data:
                self.on_alliance_selected()

            current_chronicle = self.chronicle_country_cb.get().strip()
            if current_chronicle:
                self.on_chronicle_country_selected()

        except (json.JSONDecodeError, OSError) as e:
            # 引擎採 atomic save 後通常不會遇到半份 JSON；若短暫失敗，下輪再讀即可。
            print(f"[UI 資料讀取警告]: {e}")
        except Exception as e:
            print(f"[UI 刷新警告]: {e}")
        finally:
            self.root.after(REFRESH_INTERVAL_MS, self.update_ui_data)


if __name__ == "__main__":
    game_thread = threading.Thread(target=thread_stat_monitor, daemon=True)
    game_thread.start()

    root = tk.Tk()
    app = GameInterfaceUI(root)
    root.mainloop()
