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
        # メインフレーム
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 上部：接続状態とコントロール
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 接続状態表示
        self.status_label = ttk.Label(control_frame, text="Status: Disconnected", 
                                     foreground="red")
        self.status_label.pack(side=tk.LEFT)
        
        # 開始/停止ボタン
        self.start_button = ttk.Button(control_frame, text="Start Monitoring", 
                                      command=self.start_monitoring)
        self.start_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        self.stop_button = ttk.Button(control_frame, text="Stop Monitoring", 
                                     command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_button.pack(side=tk.RIGHT)
        
        # 中央：チャートとニュースの分割
        paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)
        
        # チャート部分
        chart_frame = ttk.Frame(paned_window)
        paned_window.add(chart_frame, weight=3)
        
        chart_label = ttk.Label(chart_frame, text="LME Copper Price Chart")
        chart_label.pack()
        
        # Matplotlib図
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # ニュース部分
        news_frame = ttk.Frame(paned_window)
        paned_window.add(news_frame, weight=1)
        
        news_label = ttk.Label(news_frame, text="LME Copper News")
        news_label.pack()
        
        self.news_text = scrolledtext.ScrolledText(news_frame, height=20, width=40)
        self.news_text.pack(fill=tk.BOTH, expand=True)
        
        # 初期チャート設定
        self.setup_initial_chart()
        
    def setup_initial_chart(self):
        self.ax.set_title("LME Copper Price")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Price (USD/ton)")
        self.ax.grid(True, alpha=0.3)
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
                    self.status_label.config(text="Status: Connected to Bloomberg", 
                                           foreground="green")
                else:
                    self.status_label.config(text="Status: Failed to open market data service", 
                                           foreground="red")
            else:
                self.status_label.config(text="Status: Failed to connect to Bloomberg", 
                                       foreground="red")
                
        except Exception as e:
            self.status_label.config(text=f"Status: Connection error - {str(e)}", 
                                   foreground="red")
    
    def setup_news_session(self):
        try:
            # ニュース用の別セッション
            news_options = blpapi.SessionOptions()
            news_options.setServerHost("localhost")
            news_options.setServerPort(8194)
            
            self.news_session = blpapi.Session(news_options)
            
            if self.news_session.start():
                if self.news_session.openService("//blp/news"):
                    print("News service opened successfully")
                else:
                    print("Failed to open news service")
                    self.news_session = None
            else:
                print("Failed to start news session")
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
        
        # ニュース取得スレッド開始
        if self.news_session:
            self.news_thread = threading.Thread(target=self.bloomberg_news_thread)
            self.news_thread.daemon = True
            self.news_thread.start()
        
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
            data = {"time": datetime.datetime.now()}
            
            if msg.hasElement("LAST_PRICE"):
                data["price"] = msg.getElement("LAST_PRICE").getValueAsFloat()
            
            if msg.hasElement("BID"):
                data["bid"] = msg.getElement("BID").getValueAsFloat()
                
            if msg.hasElement("ASK"):
                data["ask"] = msg.getElement("ASK").getValueAsFloat()
                
            # デバッグ用出力
            print(f"Bloomberg Data: {data}")
            
            if "price" in data:
                self.data_queue.put(("price", data))
                
        except Exception as e:
            print(f"Error processing Bloomberg data: {e}")
    
    def bloomberg_news_thread(self):
        try:
            # ニュース検索リクエストを作成
            request = self.news_session.getService("//blp/news").createRequest("NewsHeadlineSubscription")
            
            # 銅関連のキーワードでフィルタ
            request.set("topics", ["copper", "LME", "LMCADS03"])
            request.set("maxResults", 10)
            
            # ニュース購読を開始
            self.news_session.sendRequest(request)
            
            while self.running:
                event = self.news_session.nextEvent(timeout=5000)  # 5秒タイムアウト
                
                if event.eventType() == blpapi.Event.RESPONSE or event.eventType() == blpapi.Event.PARTIAL_RESPONSE:
                    for msg in event:
                        self.process_news_data(msg)
                        
        except Exception as e:
            print(f"Bloomberg news error: {str(e)}")
            
    def process_news_data(self, msg):
        try:
            if msg.hasElement("newsHeadlines"):
                headlines = msg.getElement("newsHeadlines")
                
                for i in range(headlines.numValues()):
                    headline = headlines.getValueAsElement(i)
                    
                    news_item = {}
                    if headline.hasElement("headline"):
                        news_item["headline"] = headline.getElement("headline").getValueAsString()
                        
                    if headline.hasElement("publishedDateTime"):
                        news_item["time"] = headline.getElement("publishedDateTime").getValueAsString()
                        
                    if headline.hasElement("source"):
                        news_item["source"] = headline.getElement("source").getValueAsString()
                    
                    if news_item.get("headline"):
                        timestamp = news_item.get("time", datetime.datetime.now().strftime("%H:%M:%S"))
                        source = news_item.get("source", "Bloomberg")
                        
                        news_text = f"[{timestamp}] {source}: {news_item['headline']}"
                        self.news_queue.put(news_text)
                        
        except Exception as e:
            print(f"Error processing news data: {e}")
            
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
        
        if len(self.price_data) > 1:
            self.ax.plot(self.timestamps, self.price_data, 'b-', linewidth=2)
            
            # 最新価格をハイライト
            if self.price_data:
                latest_price = self.price_data[-1]
                latest_time = self.timestamps[-1]
                self.ax.plot(latest_time, latest_price, 'ro', markersize=8)
                
                # 価格ラベル
                self.ax.annotate(f'${latest_price:.2f}', 
                               xy=(latest_time, latest_price),
                               xytext=(10, 10), textcoords='offset points',
                               bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
        
        self.ax.set_title(f"LME Copper Price - Last: ${self.price_data[-1]:.2f}" if self.price_data else "LME Copper Price")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Price (USD/ton)")
        self.ax.grid(True, alpha=0.3)
        
        # X軸の時間フォーマット
        if self.timestamps:
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            self.ax.xaxis.set_major_locator(mdates.SecondLocator(interval=30))
            
        plt.setp(self.ax.xaxis.get_majorticklabels(), rotation=45)
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