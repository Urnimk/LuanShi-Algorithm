import os
import json
import re
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading

from 世紀帝國_AI策略強化版_戰國模式V1 import thread_stat_monitor

# ==============================================================================
# ⚙️ 全域 UI 與系統參數設定 (Global Configuration)
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. 視窗與定時器設定
# ------------------------------------------------------------------------------
# 主視窗頂部標題列所顯示的文字名稱
WINDOW_TITLE = "世紀帝國 RL 全球戰局即時監控介面"

# 應用程式啟動時的預設視窗解析度 (寬度x高度，單位：像素)
WINDOW_SIZE = "1300x850"

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
        # ⬅️ 左側分頁區域 (國家總覽 / 聯盟總覽 / 國家查詢 / 聯盟查詢)
        # ----------------------------------------------------
        self.left_notebook = ttk.Notebook(self.root)
        self.left_notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # 1. 🌐 國家總覽 Tab
        self.tab_country = ttk.Frame(self.left_notebook)
        self.left_notebook.add(self.tab_country, text=" 🌐 國家總覽 ")
        
        self.tree_country = ttk.Treeview(
            self.tab_country, 
            columns=("name", "gen", "power", "pop", "soldiers", "food", "status"), 
            show="headings"
        )
        self.tree_country.column("name", width=COL_WIDTH_COUNTRY_NAME, anchor="w")
        self.tree_country.column("gen", width=COL_WIDTH_COUNTRY_GEN, anchor="center")
        self.tree_country.column("power", width=COL_WIDTH_COUNTRY_POWER, anchor="e")
        self.tree_country.column("pop", width=COL_WIDTH_COUNTRY_POP, anchor="e")
        self.tree_country.column("soldiers", width=COL_WIDTH_COUNTRY_SOLDIERS, anchor="e")
        self.tree_country.column("food", width=COL_WIDTH_COUNTRY_FOOD, anchor="e")
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

        # 3. 🔍 單一國家詳細查詢 Tab
        # 改為固定高度「表格儀表板」，主要資訊不用滑輪往下找。
        self.tab_detail = ttk.Frame(self.left_notebook)
        self.left_notebook.add(self.tab_detail, text=" 🔍 國家詳細查詢 ")

        self.select_frame = tk.Frame(self.tab_detail, bg=COLOR_BG_MAIN)
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
        self.country_dashboard = tk.Frame(self.tab_detail, bg=COLOR_BG_MAIN)
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
            height=6,
        )
        self.country_basic_tree.heading("item", text="項目")
        self.country_basic_tree.heading("value", text="內容")
        self.country_basic_tree.column("item", width=105, anchor="w", stretch=False)
        self.country_basic_tree.column("value", width=185, anchor="w", stretch=True)
        self.country_basic_tree.pack(fill="both", expand=True, padx=4, pady=4)

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
            height=6,
        )
        self.country_econ_tree.heading("item", text="項目")
        self.country_econ_tree.heading("value", text="內容")
        self.country_econ_tree.column("item", width=105, anchor="w", stretch=False)
        self.country_econ_tree.column("value", width=185, anchor="w", stretch=True)
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
            height=3,
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
        self.country_record_area.grid_columnconfigure(0, weight=3)
        self.country_record_area.grid_columnconfigure(1, weight=2)
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
            "item", width=115, anchor="w", stretch=False
        )
        self.country_record_tree.column(
            "value", width=275, anchor="w", stretch=True
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
            "no", width=50, anchor="center", stretch=False
        )
        self.country_champion_tree.column(
            "record", width=200, anchor="w", stretch=True
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
            self.tab_detail,
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

        self.alliance_dashboard = tk.Frame(self.tab_ally_detail, bg=COLOR_BG_MAIN)
        self.alliance_dashboard.pack(fill="x", padx=8, pady=(0, 4))

        # 聯盟摘要
        self.alliance_summary_group = tk.LabelFrame(
            self.alliance_dashboard,
            text=" 🛡️ 聯盟摘要 ",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_ACCENT,
            font=FONT_UI_BOLD,
        )
        self.alliance_summary_group.pack(fill="x", pady=(0, 4))

        self.alliance_summary_tree = ttk.Treeview(
            self.alliance_summary_group,
            columns=("item", "value"),
            show="headings",
            height=5,
        )
        self.alliance_summary_tree.heading("item", text="項目")
        self.alliance_summary_tree.heading("value", text="內容")
        self.alliance_summary_tree.column("item", width=125, anchor="w", stretch=False)
        self.alliance_summary_tree.column("value", width=455, anchor="w", stretch=True)
        self.alliance_summary_tree.pack(fill="x", expand=True, padx=4, pady=4)

        # 聯盟成員明細
        self.alliance_member_group = tk.LabelFrame(
            self.alliance_dashboard,
            text=" 👥 聯盟成員明細（雙擊國家可直接查詢） ",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_ACCENT,
            font=FONT_UI_BOLD,
        )
        self.alliance_member_group.pack(fill="x", pady=(0, 4))

        self.alliance_member_tree = ttk.Treeview(
            self.alliance_member_group,
            columns=("name", "rank", "power", "pop", "soldiers", "status"),
            show="headings",
            height=9,
        )
        for col, title, width, anchor in (
            ("name", "國家", 160, "w"),
            ("rank", "排名", 120, "center"),
            ("power", "戰力", 120, "e"),
            ("pop", "人口", 120, "e"),
            ("soldiers", "士兵", 120, "e"),
            ("status", "狀態", 120, "center"),
        ):
            self.alliance_member_tree.heading(col, text=title)
            self.alliance_member_tree.column(
                col,
                width=width,
                minwidth=width,
                anchor=anchor,
                stretch=False
            )
        self.alliance_member_tree.pack(fill="x", expand=True, padx=4, pady=4)
        self.alliance_member_tree.bind("<Double-Button-1>", self.on_alliance_member_double_click)

        # 聯盟目前參與的正式戰爭
        self.alliance_war_group = tk.LabelFrame(
            self.alliance_dashboard,
            text=" ⚔️ 聯盟當前戰爭（雙擊對手可跳轉） ",
            bg=COLOR_BG_MAIN,
            fg="#FFB86C",
            font=FONT_UI_BOLD,
        )
        self.alliance_war_group.pack(fill="x")

        self.alliance_war_tree = ttk.Treeview(
            self.alliance_war_group,
            columns=("war_id", "role", "enemy", "round", "tactic"),
            show="headings",
            height=3,
        )
        for col, title, width, anchor in (
            ("war_id", "戰爭", 70, "center"),
            ("role", "立場", 85, "center"),
            ("enemy", "交戰對象", 165, "w"),
            ("round", "回合", 70, "center"),
            ("tactic", "最近戰術", 105, "center"),
        ):
            self.alliance_war_tree.heading(col, text=title)
            self.alliance_war_tree.column(col, width=width, anchor=anchor, stretch=(col == "enemy"))
        self.alliance_war_tree.pack(fill="x", expand=True, padx=4, pady=4)
        self.alliance_war_tree.bind("<Double-Button-1>", self.on_alliance_war_double_click)

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
        # ➡️ 右側區域 (右上：世界排名 / 右下：即時 LOG)
        # ----------------------------------------------------
        self.right_frame = tk.Frame(self.root, bg=COLOR_BG_MAIN)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(1, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        self.rank_group = tk.LabelFrame(
            self.right_frame, 
            text=" 🏆 世界即時排名 (點擊名稱自動查詢) ", 
            bg=COLOR_BG_MAIN, 
            fg=COLOR_FG_ACCENT, 
            font=FONT_UI_BOLD
        )
        self.rank_group.grid(row=0, column=0, sticky="nsew", pady=(0, 5))

        self.rank_text = scrolledtext.ScrolledText(
            self.rank_group, 
            bg=COLOR_BG_FIELD, 
            fg=COLOR_FG_RANK, 
            font=FONT_RANK_MONO,
            wrap=tk.WORD
        )
        self.rank_text.pack(fill="both", expand=True, padx=5, pady=5)

        self.log_group = tk.LabelFrame(
            self.right_frame, 
            text=" ⚔️ 即時戰鬥與事件 LOG ", 
            bg=COLOR_BG_MAIN, 
            fg=COLOR_FG_ACCENT, 
            font=FONT_UI_BOLD
        )
        self.log_group.grid(row=1, column=0, sticky="nsew", pady=(5, 0))

        self.log_text = scrolledtext.ScrolledText(
            self.log_group, 
            bg=COLOR_BG_DARK, 
            fg=COLOR_FG_TEXT, 
            font=FONT_LOG_TEXT,
            wrap=tk.WORD
        )
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

        self.setup_rich_log_tags(self.log_text)
        self.setup_rich_log_tags(self.country_log_text)
        self.setup_rich_log_tags(self.ally_log_text)

        self.raw_countries_data = {}
        self.raw_alliances_data = {}
        # 戰國模式進行中的正式戰爭
        self.raw_active_wars = {}

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
            ("name", "國家名稱"), ("gen", "世代"), ("power", "戰力"),
            ("pop", "總人口"), ("soldiers", "士兵"), ("food", "糧草"), ("status", "狀態")
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
        """切換到指定國家的詳細資訊頁。"""
        country_key = self.resolve_country_key(country_name)
        if not country_key:
            return False

        self.left_notebook.select(self.tab_detail)
        self.country_cb.set(country_key)
        self.on_country_selected()
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
        if os.path.exists("game.log") and terms:
            try:
                with open("game.log", "r", encoding="utf-8") as f:
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
            summary_rows[-1] = (
                "討伐目標",
                target,
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
                "存活" if c.get("is_alive", True) else "滅亡",
            )
            member_data.append((display_name, c.get("power", 0), row))

        member_data.sort(key=lambda x: x[1], reverse=True)
        max_visible_members = 9
        member_rows = [row for _name, _power, row in member_data[:max_visible_members]]

        if len(member_data) > max_visible_members:
            remaining = len(member_data) - max_visible_members
            member_rows.append(
                (f"…另有 {remaining} 國", "", "", "", "", "")
            )

        if not member_rows:
            member_rows = [("無成員", "-", "-", "-", "-", "-")]

        self._replace_tree_rows(self.alliance_member_tree, member_rows)

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

        self._replace_tree_rows(self.alliance_war_tree, war_rows[:3])

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
            result["rows"].append(
                (
                    str(war_id),
                    "進攻方" if is_attacker else "防守方",
                    enemy_name,
                    round_text,
                    self._war_tactic_name(last_tactic),
                )
            )

        result["offense"] = list(dict.fromkeys(result["offense"]))
        result["defense"] = list(dict.fromkeys(result["defense"]))
        result["log_terms"] = list(dict.fromkeys(result["log_terms"]))
        return result

    def on_country_selected(self, event=None):
        selected_name = self.country_cb.get()
        if not selected_name or selected_name not in self.raw_countries_data:
            return

        country_changed = selected_name != self._last_country_log_owner
        self._last_country_log_owner = selected_name

        c = self.raw_countries_data[selected_name]
        attackers = (
            "、".join(c.get("recent_attackers", []))
            if c.get("recent_attackers")
            else "無"
        )
        championship_records = list(
            c.get("championship_records", []) or []
        )

        current_rank = self.get_country_current_rank(selected_name)
        war_info = self.get_country_war_details(selected_name)

        # ----- 基本狀態 -----
        basic_rows = [
            (
                "國家狀態",
                "🟢 存活" if c.get("is_alive", True) else "🔴 滅亡",
            ),
            ("目前排名", current_rank),
            ("發展世代", f"第 {c.get('gen', 1)} 代"),
            ("綜合戰力", f"{c.get('power', 0):,}"),
            ("防禦工事", f"{c.get('fortification', 0)} / 100"),
            ("惡名指數", str(c.get("infamy", 0))),
        ]
        self._replace_tree_rows(self.country_basic_tree, basic_rows)

        # ----- 人口、建築與資源 -----
        pop_total = max(0, int(c.get("pop_total", 0) or 0))
        soldiers = max(0, int(c.get("soldiers", 0) or 0))
        military_ratio = soldiers / max(1, pop_total) * 100

        econ_rows = [
            (
                "房屋",
                f"{c.get('houses', 0):,} 間 / 容量 {c.get('houses', 0) * 10:,}",
            ),
            ("人口", f"{pop_total:,} 人"),
            ("農夫", f"{c.get('farmers', 0):,} 人"),
            ("士兵", f"{soldiers:,} 人（{military_ratio:.1f}%）"),
            ("糧食", f"{c.get('food', 0):,}"),
            ("木材 / 礦產", f"{c.get('wood', 0):,} / {c.get('metal', 0):,}"),
        ]
        self._replace_tree_rows(self.country_econ_tree, econ_rows)

        # ----- 當前正式戰爭 -----
        war_rows = war_info.get("rows", [])
        if not war_rows:
            war_rows = [("-", "和平", "無", "-", "-")]
        self._replace_tree_rows(self.country_war_tree, war_rows[:3])

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
                f"{c.get('wars_fought', 0)} 場｜勝 {c.get('wars_won', 0)}／敗 {c.get('wars_lost', 0)}",
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
                "奪冠次數",
                f"{c.get('championship_count', len(championship_records))} 次",
            ),
            (
                "近期攻擊來源",
                self._compact_text(attackers, 34),
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
            champion_rows.append(
                (
                    f"第 {original_no} 次",
                    str(record),
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

    def update_ui_data(self):
        """核心數據刷新機制"""
        try:
            # 1. 刷新國家資訊
            if os.path.exists("war_live_countries.json"):
                with open("war_live_countries.json", "r", encoding="utf-8") as f:
                    c_json = json.load(f)
                    self.raw_countries_data = c_json.get("countries", {})
                    
                    self.country_cb['values'] = list(self.raw_countries_data.keys())

                    for item in self.tree_country.get_children():
                        self.tree_country.delete(item)

                    for key, data in self.raw_countries_data.items():
                        disp_name = data.get("display_name", key)
                        gen = data.get("gen", 1)
                        pwr = data.get("power", 0)
                        pop = data.get("pop_total", 0)
                        soldiers = data.get("soldiers", 0)
                        food = data.get("food", 0)
                        status = "存活" if data.get("is_alive", True) else "滅亡"
                        
                        self.tree_country.insert("", "end", values=(disp_name, gen, pwr, pop, soldiers, food, status))

                    col, rev = self.country_sort_state
                    self.apply_sort(self.tree_country, col, rev)

            # 2. 刷新聯盟資訊與下拉選單
            if os.path.exists("war_live_alliances.json"):
                with open("war_live_alliances.json", "r", encoding="utf-8") as f:
                    a_json = json.load(f)
                    self.raw_alliances_data = a_json.get("alliance_details", {})
                    self.raw_active_wars = a_json.get("active_wars", {}) or {}

                    self.ally_cb['values'] = list(self.raw_alliances_data.keys())

                    for item in self.tree_alliance.get_children():
                        self.tree_alliance.delete(item)

                    for ally_name, details in self.raw_alliances_data.items():
                        pwr = details.get("total_power", 0)
                        m_count = f"{details.get('alive_member_count', 0)}/{details.get('member_count', 0)}"
                        target = details.get("target_hegemon", "無") or "無"
                        
                        self.tree_alliance.insert("", "end", values=(ally_name, pwr, m_count, target))

                    col, rev = self.alliance_sort_state
                    self.apply_sort(self.tree_alliance, col, rev)

            # 3. 刷新右上角排名
            if os.path.exists("Live_Ranking.txt"):
                with open("Live_Ranking.txt", "r", encoding="utf-8") as f:
                    content = f.read()

                self.rank_text.tag_config("alliance_yellow", foreground=COLOR_FG_YELLOW, font=(FONT_FAMILY_MONO, FONT_SIZE_RANK, "bold"))

                if self.rank_text.get("1.0", tk.END).strip() != content.strip():
                    self.rank_text.config(state=tk.NORMAL)
                    self.rank_text.delete("1.0", tk.END)
                    self.rank_text.insert(tk.END, content)

                    for ally_name in self.raw_alliances_data.keys():
                        if not ally_name: continue
                        start_pos = "1.0"
                        while True:
                            pos = self.rank_text.search(ally_name, start_pos, stopindex=tk.END)
                            if not pos: break
                            end_pos = f"{pos}+{len(ally_name)}c"
                            self.rank_text.tag_add("alliance_yellow", pos, end_pos)
                            start_pos = end_pos

                    # 國家與聯盟名稱都加上可點擊超連結外觀。
                    self.apply_entity_link_tags(self.rank_text)

            # 4. 刷新右下角全域 LOG
            if os.path.exists("game.log"):
                with open("game.log", "r", encoding="utf-8") as f:
                    lines = f.readlines()[:MAX_GLOBAL_LOG_LINES]
                    
                    self.log_text.config(state=tk.NORMAL)
                    self.log_text.delete("1.0", tk.END)
                    
                    for line in lines:
                        self.append_rich_log_line_to_widget(self.log_text, line.strip())

                    self.apply_entity_link_tags(self.log_text)
                    self.log_text.see("1.0")

            # 5. 當前選中的詳細頁面同步動態刷新
            current_country = self.country_cb.get().strip()
            if current_country and current_country in self.raw_countries_data:
                self.on_country_selected()

            current_ally = self.ally_cb.get().strip()
            if current_ally and current_ally in self.raw_alliances_data:
                self.on_alliance_selected()

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