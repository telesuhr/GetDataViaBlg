import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import threading
import queue
import datetime
import time
import numpy as np

try:
    import blpapi
    BLPAPI_AVAILABLE = True
except ImportError:
    BLPAPI_AVAILABLE = False
    print("Warning: Bloomberg API not available. Using demo mode.")

class LMECopperMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("LME Copper Monitor - Bloomberg API")
        self.root.geometry("1200x800")
        
        # データ格納用
        self.price_data = []
        self.timestamps = []
        self.news_data = []
        
        # Bloomberg API関連
        self.session = None
        self.subscription_list = None
        self.news_session = None
        self.running = False
        
        # キューでスレッド間通信
        self.data_queue = queue.Queue()
        self.news_queue = queue.Queue()
        
        self.setup_ui()
        self.setup_bloomberg_connection()
        
    def setup_ui(self):
        # メインウィンドウのスタイル設定
        self.root.configure(bg='#1a1a1a')  # ダークテーマ
        
        # スタイル設定
        style = ttk.Style()
        style.theme_use('clam')
        
        # カスタムスタイル定義
        style.configure('Header.TLabel', 
                       background='#1a1a1a', 
                       foreground='#ffffff',
                       font=('Arial', 16, 'bold'))
        
        style.configure('Status.TLabel',
                       background='#1a1a1a',
                       foreground='#00ff00',
                       font=('Arial', 11, 'bold'))
        
        style.configure('Modern.TButton',
                       background='#4a9eff',
                       foreground='white',
                       font=('Arial', 10, 'bold'),
                       padding=10)
        
        style.map('Modern.TButton',
                 background=[('active', '#3d8bdb'),
                           ('pressed', '#2e69a3')])
        
        # メインフレーム
        main_frame = tk.Frame(self.root, bg='#1a1a1a')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # ヘッダー部分
        header_frame = tk.Frame(main_frame, bg='#1a1a1a')
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        # タイトル
        title_label = tk.Label(header_frame, 
                              text="🔥 LME Copper Real-Time Monitor", 
                              bg='#1a1a1a', 
                              fg='#ffffff',
                              font=('Arial', 20, 'bold'))
        title_label.pack(side=tk.TOP, pady=(0, 10))
        
        # 上部：接続状態とコントロール
        control_frame = tk.Frame(header_frame, bg='#1a1a1a')
        control_frame.pack(fill=tk.X)
        
        # 接続状態表示（カード風）
        status_card = tk.Frame(control_frame, bg='#2d2d2d', relief='flat', bd=1)
        status_card.pack(side=tk.LEFT, padx=(0, 20), pady=5, ipadx=15, ipady=8)
        
        status_icon = tk.Label(status_card, text="●", bg='#2d2d2d', fg='#ff4444', font=('Arial', 14))
        status_icon.pack(side=tk.LEFT, padx=(0, 8))
        
        self.status_label = tk.Label(status_card, text="Disconnected", 
                                   bg='#2d2d2d', fg='#ffffff',
                                   font=('Arial', 11, 'bold'))
        self.status_label.pack(side=tk.LEFT)
        
        # ボタンフレーム
        button_frame = tk.Frame(control_frame, bg='#1a1a1a')
        button_frame.pack(side=tk.RIGHT)
        
        # 開始ボタン（グラデーション風）
        self.start_button = tk.Button(button_frame, 
                                     text="▶ Start Monitoring", 
                                     command=self.start_monitoring,
                                     bg='#4CAF50',
                                     fg='white',
                                     font=('Arial', 11, 'bold'),
                                     relief='flat',
                                     padx=20,
                                     pady=8,
                                     cursor='hand2')
        self.start_button.pack(side=tk.RIGHT, padx=5)
        
        # 停止ボタン
        self.stop_button = tk.Button(button_frame, 
                                    text="⏸ Stop Monitoring", 
                                    command=self.stop_monitoring, 
                                    state=tk.DISABLED,
                                    bg='#f44336',
                                    fg='white',
                                    font=('Arial', 11, 'bold'),
                                    relief='flat',
                                    padx=20,
                                    pady=8,
                                    cursor='hand2')
        self.stop_button.pack(side=tk.RIGHT, padx=5)
        
        # メインコンテンツエリア
        content_frame = tk.Frame(main_frame, bg='#1a1a1a')
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # チャート部分（カード風）
        chart_card = tk.Frame(content_frame, bg='#2d2d2d', relief='flat', bd=1)
        chart_card.pack(fill=tk.BOTH, expand=True, padx=(0, 10), pady=5, side=tk.LEFT)
        
        # チャートヘッダー
        chart_header = tk.Frame(chart_card, bg='#2d2d2d')
        chart_header.pack(fill=tk.X, padx=15, pady=(15, 10))
        
        chart_title = tk.Label(chart_header, 
                              text="📈 Price Chart", 
                              bg='#2d2d2d', 
                              fg='#ffffff',
                              font=('Arial', 14, 'bold'))
        chart_title.pack(side=tk.LEFT)
        
        # 現在価格表示
        self.price_label = tk.Label(chart_header,
                                   text="$0.00",
                                   bg='#2d2d2d',
                                   fg='#4CAF50',
                                   font=('Arial', 16, 'bold'))
        self.price_label.pack(side=tk.RIGHT)
        
        # Matplotlib図（ダークテーマ）
        self.fig = Figure(figsize=(10, 6), dpi=100, facecolor='#2d2d2d')
        self.ax = self.fig.add_subplot(111, facecolor='#1a1a1a')
        self.canvas = FigureCanvasTkAgg(self.fig, chart_card)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        # サイドパネル（統計情報）
        side_panel = tk.Frame(content_frame, bg='#2d2d2d', width=300, relief='flat', bd=1)
        side_panel.pack(fill=tk.Y, side=tk.RIGHT, padx=(10, 0), pady=5)
        side_panel.pack_propagate(False)
        
        # サイドパネルヘッダー
        side_header = tk.Label(side_panel, 
                              text="📊 Market Statistics", 
                              bg='#2d2d2d', 
                              fg='#ffffff',
                              font=('Arial', 14, 'bold'))
        side_header.pack(pady=(15, 20))
        
        # 統計情報カード
        self.create_stat_card(side_panel, "High", "$0.00", "#4CAF50")
        self.create_stat_card(side_panel, "Low", "$0.00", "#f44336")
        self.create_stat_card(side_panel, "Change", "0.00%", "#FF9800")
        self.create_stat_card(side_panel, "Volume", "0", "#2196F3")
        
        # ニュースセクション（小さく）
        news_section = tk.Frame(side_panel, bg='#2d2d2d')
        news_section.pack(fill=tk.BOTH, expand=True, padx=15, pady=(20, 15))
        
        news_title = tk.Label(news_section, 
                             text="📰 Market Updates", 
                             bg='#2d2d2d', 
                             fg='#ffffff',
                             font=('Arial', 12, 'bold'))
        news_title.pack(pady=(0, 10))
        
        self.news_text = tk.Text(news_section, 
                                height=8, 
                                bg='#1a1a1a',
                                fg='#cccccc',
                                font=('Consolas', 9),
                                relief='flat',
                                wrap=tk.WORD)
        self.news_text.pack(fill=tk.BOTH, expand=True)
        
        # 初期チャート設定
        self.setup_initial_chart()
        
    def create_stat_card(self, parent, title, value, color):
        """統計情報カードを作成"""
        card = tk.Frame(parent, bg='#1a1a1a', relief='flat', bd=1)
        card.pack(fill=tk.X, padx=15, pady=5, ipady=10)
        
        title_label = tk.Label(card, text=title, bg='#1a1a1a', fg='#888888', font=('Arial', 10))
        title_label.pack()
        
        value_label = tk.Label(card, text=value, bg='#1a1a1a', fg=color, font=('Arial', 14, 'bold'))
        value_label.pack()
        
        # 統計ラベルを保存（後で更新用）
        if not hasattr(self, 'stat_labels'):
            self.stat_labels = {}
        self.stat_labels[title.lower()] = value_label
        
    def setup_initial_chart(self):
        # ダークテーマでチャートを設定
        self.ax.set_title("LME Copper Price", color='white', fontsize=14, pad=20)
        self.ax.set_xlabel("Time", color='white', fontsize=11)
        self.ax.set_ylabel("Price (USD/ton)", color='white', fontsize=11)
        
        # グリッドの設定
        self.ax.grid(True, alpha=0.2, color='#444444', linestyle='-', linewidth=0.5)
        
        # 軸の色を設定
        self.ax.tick_params(colors='white', labelsize=9)
        self.ax.spines['bottom'].set_color('#444444')
        self.ax.spines['top'].set_color('#444444')
        self.ax.spines['right'].set_color('#444444')
        self.ax.spines['left'].set_color('#444444')
        
        # 背景色設定
        self.ax.set_facecolor('#1a1a1a')
        self.fig.patch.set_facecolor('#2d2d2d')
        
        self.canvas.draw()
        
    def setup_bloomberg_connection(self):
        if not BLPAPI_AVAILABLE:
            self.status_label.config(text="Status: Bloomberg API not available (Demo mode)", 
                                   foreground="orange")
            return
            
        try:
            # Bloomberg API接続設定
            session_options = blpapi.SessionOptions()
            session_options.setServerHost("localhost")
            session_options.setServerPort(8194)
            
            self.session = blpapi.Session(session_options)
            
            if self.session.start():
                if self.session.openService("//blp/mktdata"):
                    # ニュース用セッションも開始
                    self.setup_news_session()
                    self.status_label.config(text="Connected to Bloomberg", fg="#4CAF50")
                    # ステータスアイコンも更新
                    status_icon = self.status_label.master.winfo_children()[0]
                    status_icon.config(fg="#4CAF50")
                else:
                    self.status_label.config(text="Failed to open market data service", fg="#f44336")
            else:
                self.status_label.config(text="Failed to connect to Bloomberg", fg="#f44336")
                
        except Exception as e:
            self.status_label.config(text=f"Status: Connection error - {str(e)}", 
                                   foreground="red")
    
    def setup_news_session(self):
        try:
            # 既存のセッションでニュースサービスを試行
            if self.session:
                # 利用可能なニュースサービスを試行
                news_services = [
                    "//blp/refdata",  # Reference Data Service (ニュース含む)
                    "//blp/apiflds",  # API Fields Service  
                    "//blp/instruments" # Instruments Service
                ]
                
                for service_name in news_services:
                    try:
                        if self.session.openService(service_name):
                            print(f"Opened service: {service_name}")
                            self.news_session = self.session
                            return
                    except Exception as e:
                        print(f"Failed to open {service_name}: {e}")
                        continue
                
                print("No news services available, will use web scraping fallback")
                self.news_session = None
            else:
                self.news_session = None
                
        except Exception as e:
            print(f"Error setting up news session: {e}")
            self.news_session = None
            
    def start_monitoring(self):
        if not BLPAPI_AVAILABLE:
            self.start_demo_mode()
            return
            
        if not self.session:
            messagebox.showerror("Error", "Bloomberg connection not available")
            return
            
        self.running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # リアルタイムデータ取得スレッド開始
        self.data_thread = threading.Thread(target=self.bloomberg_data_thread)
        self.data_thread.daemon = True
        self.data_thread.start()
        
        
        # UI更新スレッド開始
        self.update_ui_thread()
        
    def start_demo_mode(self):
        self.running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # デモデータ生成スレッド
        self.demo_thread = threading.Thread(target=self.demo_data_thread)
        self.demo_thread.daemon = True
        self.demo_thread.start()
        
        
        self.update_ui_thread()
        
    def bloomberg_data_thread(self):
        try:
            # LME Copper銘柄コード - 正しいBloomberg形式
            subscriptions = blpapi.SubscriptionList()
            subscriptions.add("LMCADS03 Comdty", "LAST_PRICE,BID,ASK")  # LME Copper 3-month
            
            self.session.subscribe(subscriptions)
            
            while self.running:
                event = self.session.nextEvent(timeout=1000)
                
                if event.eventType() == blpapi.Event.SUBSCRIPTION_DATA:
                    for msg in event:
                        self.process_bloomberg_data(msg)
                        
        except Exception as e:
            self.data_queue.put(("error", f"Bloomberg data error: {str(e)}"))
            
    def process_bloomberg_data(self, msg):
        try:
            if msg.hasElement("LAST_PRICE"):
                price = msg.getElement("LAST_PRICE").getValueAsFloat()
                timestamp = datetime.datetime.now()
                
                data = {"price": price, "time": timestamp}
                self.data_queue.put(("price", data))
                
        except Exception as e:
            print(f"Error processing Bloomberg data: {e}")
    
    def news_thread_manager(self):
        """ニューススレッドの管理"""
        if self.news_session:
            print("Starting Bloomberg news thread...")
            self.bloomberg_news_thread()
        else:
            print("Bloomberg news service not available")
    
    def bloomberg_news_thread(self):
        try:
            # Reference Data Service経由でニュース関連フィールドを取得
            if self.news_session.openService("//blp/refdata"):
                service = self.news_session.getService("//blp/refdata")
                print("Using Reference Data Service for news-related data")
                
                # ニュース関連フィールドの取得
                request = service.createRequest("ReferenceDataRequest")
                request.getElement("securities").appendValue("LMCADS03 Comdty")
                
                # ニュース関連のフィールドを試行
                fields = ["NEWS_COUNT", "LAST_UPDATE_DT", "NAME", "SECURITY_DES"]
                for field in fields:
                    request.getElement("fields").appendValue(field)
                
                print("Requesting reference data with news fields...")
                
                while self.running:
                    self.fetch_reference_data(service, request)
                    time.sleep(300)  # 5分間隔で更新
                    
            else:
                print("Failed to open Reference Data Service")
                
        except Exception as e:
            print(f"Bloomberg news thread error: {str(e)}")
    
    def fetch_reference_data(self, service, request):
        """Reference Data取得処理"""
        try:
            self.news_session.sendRequest(request)
            
            timeout_counter = 0
            while timeout_counter < 10:
                event = self.news_session.nextEvent(timeout=1000)
                
                if event.eventType() == blpapi.Event.RESPONSE:
                    print("Received reference data response")
                    for msg in event:
                        self.process_reference_data(msg)
                    break
                elif event.eventType() == blpapi.Event.PARTIAL_RESPONSE:
                    for msg in event:
                        self.process_reference_data(msg)
                
                timeout_counter += 1
                        
        except Exception as e:
            print(f"Error fetching reference data: {str(e)}")
    
    def process_reference_data(self, msg):
        """Reference Dataの処理"""
        try:
            print(f"Full message content: {msg}")
            
            if msg.hasElement("securityData"):
                security_data = msg.getElement("securityData")
                print(f"Found {security_data.numValues()} securities")
                
                for i in range(security_data.numValues()):
                    security = security_data.getValueAsElement(i)
                    
                    sec_name = "Unknown"
                    if security.hasElement("security"):
                        sec_name = security.getElement("security").getValueAsString()
                        print(f"Processing security: {sec_name}")
                        
                    if security.hasElement("fieldData"):
                        field_data = security.getElement("fieldData")
                        print(f"Field data available for {sec_name}")
                        
                        # すべての利用可能なフィールドをデバッグ出力
                        for j in range(field_data.numElements()):
                            element = field_data.getElement(j)
                            field_name = element.name()
                            try:
                                field_value = element.getValueAsString()
                                print(f"  {field_name}: {field_value}")
                            except:
                                print(f"  {field_name}: [complex data]")
                        
                        # 基本情報をニュースパネルに表示
                        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                        
                        if field_data.hasElement("NAME"):
                            name = field_data.getElement("NAME").getValueAsString()
                            news_text = f"[{timestamp}] {sec_name}: {name}"
                            self.news_queue.put(news_text)
                            print(f"Added news: {news_text}")
                            
                        if field_data.hasElement("LAST_UPDATE_DT"):
                            last_update = field_data.getElement("LAST_UPDATE_DT").getValueAsString()
                            news_text = f"[{timestamp}] Last Update: {last_update}"
                            self.news_queue.put(news_text)
                            print(f"Added news: {news_text}")
                            
                        # セキュリティ説明があれば表示
                        if field_data.hasElement("SECURITY_DES"):
                            desc = field_data.getElement("SECURITY_DES").getValueAsString()
                            news_text = f"[{timestamp}] Description: {desc}"
                            self.news_queue.put(news_text)
                            print(f"Added news: {news_text}")
                            
                    if security.hasElement("fieldExceptions"):
                        exceptions = security.getElement("fieldExceptions")
                        print(f"Field exceptions for {sec_name}:")
                        for j in range(exceptions.numValues()):
                            exception = exceptions.getValueAsElement(j)
                            if exception.hasElement("fieldId"):
                                field_id = exception.getElement("fieldId").getValueAsString()
                                print(f"  Exception for field: {field_id}")
                        
        except Exception as e:
            print(f"Error processing reference data: {e}")
            import traceback
            traceback.print_exc()
            
    def process_news_data(self, msg):
        try:
            print(f"Processing news message type: {msg.messageType()}")
            
            # Bloomberg News APIの様々なレスポンス形式に対応
            if msg.hasElement("newsItems") or msg.hasElement("GetNewsResponse"):
                news_items = None
                
                # レスポンス形式を特定
                if msg.hasElement("GetNewsResponse"):
                    response = msg.getElement("GetNewsResponse")
                    if response.hasElement("newsItems"):
                        news_items = response.getElement("newsItems")
                elif msg.hasElement("newsItems"):
                    news_items = msg.getElement("newsItems")
                
                if news_items and news_items.numValues() > 0:
                    print(f"Found {news_items.numValues()} news items")
                    
                    for i in range(news_items.numValues()):
                        item = news_items.getValueAsElement(i)
                        
                        headline = ""
                        source = "Bloomberg"
                        published_time = ""
                        
                        # ヘッドライン取得
                        if item.hasElement("headline"):
                            headline = item.getElement("headline").getValueAsString()
                        elif item.hasElement("title"):
                            headline = item.getElement("title").getValueAsString()
                            
                        # ソース取得
                        if item.hasElement("source"):
                            source = item.getElement("source").getValueAsString()
                        elif item.hasElement("provider"):
                            source = item.getElement("provider").getValueAsString()
                            
                        # 公開時刻取得
                        if item.hasElement("publishedDateTime"):
                            published_time = item.getElement("publishedDateTime").getValueAsString()
                        elif item.hasElement("dateTime"):
                            published_time = item.getElement("dateTime").getValueAsString()
                        else:
                            published_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        if headline:
                            # 時刻フォーマットを調整
                            try:
                                if "T" in published_time:
                                    dt = datetime.datetime.fromisoformat(published_time.replace("Z", "+00:00"))
                                    time_str = dt.strftime("%H:%M")
                                else:
                                    time_str = published_time
                            except:
                                time_str = datetime.datetime.now().strftime("%H:%M")
                            
                            news_text = f"[{time_str}] {source}: {headline}"
                            self.news_queue.put(news_text)
                            print(f"Added news: {news_text}")
                else:
                    print("No news items found in response")
            else:
                print("No recognized news elements in message")
                        
        except Exception as e:
            print(f"Error processing news data: {e}")
            import traceback
            traceback.print_exc()
            
    def demo_data_thread(self):
        base_price = 8500  # USD/ton
        
        while self.running:
            # ランダムな価格変動を生成
            change = np.random.normal(0, 20)  # 平均0、標準偏差20の変動
            price = base_price + change
            base_price = price
            
            timestamp = datetime.datetime.now()
            
            self.data_queue.put(("price", {"price": price, "time": timestamp}))
            
            # デモニュース
            if np.random.random() < 0.1:  # 10%の確率でニュース
                news_items = [
                    "LME copper stocks rise 2% on increased supply",
                    "China demand for copper shows signs of recovery",
                    "Copper futures gain on supply concerns",
                    "Mining strikes could impact copper production",
                    "Copper demand expected to surge with green energy transition"
                ]
                news = np.random.choice(news_items)
                self.news_queue.put(f"{timestamp.strftime('%H:%M:%S')} - {news}")
            
            time.sleep(2)  # 2秒間隔
            
    def update_ui_thread(self):
        try:
            # データキューから価格データを取得
            while not self.data_queue.empty():
                data_type, data = self.data_queue.get_nowait()
                
                if data_type == "price":
                    self.price_data.append(data["price"])
                    self.timestamps.append(data["time"])
                    
                    # 最新100件のデータのみ保持
                    if len(self.price_data) > 100:
                        self.price_data.pop(0)
                        self.timestamps.pop(0)
                        
                elif data_type == "error":
                    messagebox.showerror("Error", data)
                    
            # ニュースキューからニュースを取得
            while not self.news_queue.empty():
                news = self.news_queue.get_nowait()
                self.news_text.insert(tk.END, news + "\n")
                self.news_text.see(tk.END)
                
            # チャート更新
            if self.price_data and self.running:
                self.update_chart()
                
        except queue.Empty:
            pass
        except Exception as e:
            print(f"UI update error: {e}")
            
        # 継続的な更新
        if self.running:
            self.root.after(1000, self.update_ui_thread)  # 1秒間隔
            
    def update_chart(self):
        self.ax.clear()
        
        # チャートスタイルを再設定
        self.ax.set_facecolor('#1a1a1a')
        self.ax.tick_params(colors='white', labelsize=9)
        self.ax.spines['bottom'].set_color('#444444')
        self.ax.spines['top'].set_color('#444444')
        self.ax.spines['right'].set_color('#444444')
        self.ax.spines['left'].set_color('#444444')
        
        if len(self.price_data) > 1:
            # グラデーション効果のある線
            self.ax.plot(self.timestamps, self.price_data, 
                        color='#00ff88', linewidth=2.5, alpha=0.9)
            
            # エリアチャート（塗りつぶし）
            self.ax.fill_between(self.timestamps, self.price_data, 
                               alpha=0.2, color='#00ff88')
            
            # 最新価格をハイライト
            if self.price_data:
                latest_price = self.price_data[-1]
                latest_time = self.timestamps[-1]
                
                # 大きな点
                self.ax.plot(latest_time, latest_price, 'o', 
                           color='#ffff00', markersize=12, alpha=0.8)
                self.ax.plot(latest_time, latest_price, 'o', 
                           color='#ff4444', markersize=8)
                
                # 価格ラベル（モダンスタイル）
                self.ax.annotate(f'${latest_price:.2f}', 
                               xy=(latest_time, latest_price),
                               xytext=(15, 15), textcoords='offset points',
                               bbox=dict(boxstyle='round,pad=0.5', 
                                       facecolor='#4CAF50', 
                                       edgecolor='none',
                                       alpha=0.9),
                               color='white',
                               fontweight='bold',
                               fontsize=11)
                
                # 現在価格をヘッダーに更新
                self.price_label.config(text=f"${latest_price:.2f}")
                
                # 統計情報を更新
                if len(self.price_data) > 1:
                    high_price = max(self.price_data)
                    low_price = min(self.price_data)
                    change_pct = ((latest_price - self.price_data[0]) / self.price_data[0]) * 100
                    
                    self.stat_labels['high'].config(text=f"${high_price:.2f}")
                    self.stat_labels['low'].config(text=f"${low_price:.2f}")
                    self.stat_labels['change'].config(
                        text=f"{change_pct:+.2f}%",
                        fg='#4CAF50' if change_pct >= 0 else '#f44336'
                    )
                    self.stat_labels['volume'].config(text=str(len(self.price_data)))
        
        # タイトルとラベル（ダークテーマ）
        self.ax.set_title("Real-Time Price Movement", 
                         color='white', fontsize=12, pad=15)
        self.ax.set_xlabel("Time", color='white', fontsize=10)
        self.ax.set_ylabel("Price (USD/ton)", color='white', fontsize=10)
        
        # グリッド
        self.ax.grid(True, alpha=0.2, color='#444444', linestyle='-', linewidth=0.5)
        
        # X軸の時間フォーマット
        if self.timestamps:
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            self.ax.xaxis.set_major_locator(mdates.SecondLocator(interval=30))
            
        plt.setp(self.ax.xaxis.get_majorticklabels(), rotation=45, color='white')
        plt.setp(self.ax.yaxis.get_majorticklabels(), color='white')
        
        self.fig.tight_layout()
        self.canvas.draw()
        
    def stop_monitoring(self):
        self.running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        if self.session:
            try:
                self.session.stop()
            except Exception as e:
                print(f"Error stopping session: {e}")
                
        if self.news_session:
            try:
                self.news_session.stop()
            except Exception as e:
                print(f"Error stopping news session: {e}")
            
    def on_closing(self):
        self.stop_monitoring()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = LMECopperMonitor(root)
    
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()