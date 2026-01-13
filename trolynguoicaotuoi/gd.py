import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import os
import threading
import datetime
import time
import random
import string
import sqlite3
from PIL import Image, ImageTk, ImageDraw

# Thư viện âm thanh & Giọng nói
from gtts import gTTS
import pygame
import speech_recognition as sr

# Thư viện vẽ biểu đồ
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates

# =====================================================
# 1. QUẢN LÝ DATABASE (SQLite)
# =====================================================
def init_db():
    conn = sqlite3.connect('elder_care_v2.db') # Đổi tên DB để tránh xung đột dữ liệu cũ
    c = conn.cursor()
    # Bảng người dùng
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT, 
        full_name TEXT,
        gender TEXT,
        address_term TEXT, 
        link_code TEXT, 
        linked_to INTEGER 
    )''')
    # Bảng lịch sử (Thêm cột timestamp để vẽ biểu đồ chính xác theo giờ)
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date_str TEXT,     -- Lưu ngày hiển thị (VD: 20/10)
        timestamp REAL,    -- Lưu thời gian thực (số giây) để sort
        mood_score INTEGER, 
        mood_label TEXT,
        chat_content TEXT
    )''')
    # Bảng nhân vật
    c.execute('''CREATE TABLE IF NOT EXISTS companions (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        avatar_path TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect('elder_care_v2.db')

# =====================================================
# 2. XỬ LÝ GIỌNG NÓI & AI
# =====================================================
def speak_ai(text):
    def run():
        try:
            tts = gTTS(text=text, lang='vi')
            filename = f"voice_{int(time.time())}_{random.randint(0,999)}.mp3"
            tts.save(filename)
            pygame.mixer.init()
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.quit()
            os.remove(filename)
        except Exception as e:
            print(f"Lỗi Audio: {e}")
    threading.Thread(target=run).start()

def listen_mic():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Đang nghe...")
        try:
            # Tự động điều chỉnh tiếng ồn nền
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source, timeout=4, phrase_time_limit=6)
            text = r.recognize_google(audio, language="vi-VN")
            return text
        except:
            return None

# =====================================================
# 3. GIAO DIỆN & LOGIC
# =====================================================

# --- Helper: Tạo ảnh mẫu & Gradient Mịn ---
if not os.path.exists("assets"): os.makedirs("assets")

def create_gradient(width, height, c1, c2):
    """Tạo gradient mịn bằng Pillow (Fix lỗi sọc ngang)"""
    if width <=1 or height <=1: return Image.new('RGB', (1,1), c1)
    base = Image.new('RGB', (width, height), c1)
    top = Image.new('RGB', (width, height), c2)
    mask = Image.new('L', (width, height))
    mask_data = []
    for y in range(height):
        # Tính toán độ mờ dần theo chiều dọc
        mask_data.extend([int(255*(y/height))]*width)
    mask.putdata(mask_data)
    base.paste(top, (0,0), mask)
    return base

class BaseFrame(ctk.CTkFrame):
    def __init__(self, parent, c1, c2, **kwargs):
        super().__init__(parent, **kwargs)
        self.c1, self.c2 = c1, c2
        self.bg = tk.Label(self, borderwidth=0)
        self.bg.place(x=0, y=0, relwidth=1, relheight=1)
        self.bind("<Configure>", self.upd)
    def upd(self, e):
        if e.width>50 and e.height>50:
            self.im = ImageTk.PhotoImage(create_gradient(e.width, e.height, self.c1, self.c2))
            self.bg.config(image=self.im)

# --- MÀN HÌNH ĐĂNG NHẬP ---
class AuthFrame(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, "#4facfe", "#00f2fe")
        self.controller = controller
        
        # Tiêu đề (Fix lỗi #00000030 bằng cách dùng màu xám đậm)
        ctk.CTkLabel(self, text="SMART ELDER COMPANION", font=("Arial", 30, "bold"), text_color="#333", bg_color="transparent").place(relx=0.502, rely=0.103, anchor="center")
        ctk.CTkLabel(self, text="SMART ELDER COMPANION", font=("Arial", 30, "bold"), text_color="white", bg_color="transparent").place(relx=0.5, rely=0.1, anchor="center")

        self.frame = ctk.CTkFrame(self, fg_color="white", corner_radius=15)
        self.frame.place(relx=0.5, rely=0.55, anchor="center")
        
        self.notebook = ctk.CTkTabview(self.frame, width=400, height=450)
        self.notebook.pack(padx=20, pady=20)
        
        self.tab_login = self.notebook.add("Đăng Nhập")
        self.tab_register = self.notebook.add("Đăng Ký")
        
        self.setup_login()
        self.setup_register()

    def setup_login(self):
        ctk.CTkLabel(self.tab_login, text="Tên đăng nhập:").pack(pady=5)
        self.entry_log_user = ctk.CTkEntry(self.tab_login, width=250)
        self.entry_log_user.pack(pady=5)
        ctk.CTkLabel(self.tab_login, text="Mật khẩu:").pack(pady=5)
        self.entry_log_pass = ctk.CTkEntry(self.tab_login, width=250, show="*")
        self.entry_log_pass.pack(pady=5)
        ctk.CTkButton(self.tab_login, text="ĐĂNG NHẬP", command=self.login).pack(pady=20)

    def setup_register(self):
        self.role_var = ctk.StringVar(value="elder")
        def toggle_role():
            if self.role_var.get() == "relative":
                self.entry_link_code.pack(pady=5)
                self.lbl_link.pack(pady=5)
                self.entry_addr.pack_forget()
                self.lbl_addr.pack_forget()
            else:
                self.entry_link_code.pack_forget()
                self.lbl_link.pack_forget()
                self.lbl_addr.pack(pady=5)
                self.entry_addr.pack(pady=5)

        ctk.CTkRadioButton(self.tab_register, text="Người Lớn Tuổi", variable=self.role_var, value="elder", command=toggle_role).pack(pady=5)
        ctk.CTkRadioButton(self.tab_register, text="Người Thân", variable=self.role_var, value="relative", command=toggle_role).pack(pady=5)

        self.entry_reg_user = ctk.CTkEntry(self.tab_register, placeholder_text="Tên đăng nhập", width=250)
        self.entry_reg_user.pack(pady=5)
        self.entry_reg_pass = ctk.CTkEntry(self.tab_register, placeholder_text="Mật khẩu", show="*", width=250)
        self.entry_reg_pass.pack(pady=5)
        self.entry_name = ctk.CTkEntry(self.tab_register, placeholder_text="Họ và Tên", width=250)
        self.entry_name.pack(pady=5)
        self.entry_gender = ctk.CTkComboBox(self.tab_register, values=["Nam", "Nữ"], width=250)
        self.entry_gender.pack(pady=5)
        
        self.lbl_addr = ctk.CTkLabel(self.tab_register, text="Cách xưng hô (Bác/Chú...):")
        self.lbl_addr.pack(pady=5)
        self.entry_addr = ctk.CTkEntry(self.tab_register, width=250)
        self.entry_addr.pack(pady=5)
        
        self.lbl_link = ctk.CTkLabel(self.tab_register, text="Nhập mã liên kết:")
        self.entry_link_code = ctk.CTkEntry(self.tab_register, placeholder_text="Mã lấy từ máy người già", width=250)
        self.lbl_link.pack_forget()
        self.entry_link_code.pack_forget()

        ctk.CTkButton(self.tab_register, text="ĐĂNG KÝ", command=self.register).pack(pady=20)

    def register(self):
        user = self.entry_reg_user.get()
        pwd = self.entry_reg_pass.get()
        role = self.role_var.get()
        name = self.entry_name.get()
        gender = self.entry_gender.get()
        conn = get_db_connection()
        c = conn.cursor()
        try:
            if role == "elder":
                addr = self.entry_addr.get()
                link_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                c.execute("INSERT INTO users (username, password, role, full_name, gender, address_term, link_code) VALUES (?,?,?,?,?,?,?)",
                          (user, pwd, role, name, gender, addr, link_code))
                messagebox.showinfo("Thành công", f"Đăng ký thành công!\nMã liên kết: {link_code}\n(Hãy ghi lại mã này để đưa cho con cháu)")
            else:
                link_code_input = self.entry_link_code.get().upper()
                c.execute("SELECT id FROM users WHERE link_code=?", (link_code_input,))
                elder = c.fetchone()
                if not elder:
                    messagebox.showerror("Lỗi", "Mã liên kết không đúng!")
                    return
                c.execute("INSERT INTO users (username, password, role, full_name, gender, linked_to) VALUES (?,?,?,?,?,?)",
                          (user, pwd, role, name, gender, elder[0]))
                messagebox.showinfo("Thành công", "Đã liên kết với người thân!")
            conn.commit()
            self.notebook.set("Đăng Nhập")
        except sqlite3.IntegrityError:
            messagebox.showerror("Lỗi", "Tên đăng nhập đã tồn tại.")
        finally:
            conn.close()

    def login(self):
        user = self.entry_log_user.get()
        pwd = self.entry_log_pass.get()
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, pwd))
        data = c.fetchone()
        conn.close()
        if data:
            self.controller.current_user = data
            if data[3] == "elder":
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("SELECT * FROM companions WHERE user_id=?", (data[0],))
                comp = c.fetchone()
                conn.close()
                if comp: self.controller.show_frame("ElderHome")
                else: self.controller.show_frame("SetupCompanion")
            else:
                self.controller.show_frame("RelativeHome")
        else:
            messagebox.showerror("Lỗi", "Sai thông tin đăng nhập")

# --- MÀN HÌNH CHỌN NHÂN VẬT ---
class SetupCompanion(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, "#a18cd1", "#fbc2eb")
        self.controller = controller
        
        ctk.CTkLabel(self, text="CHỌN BẠN ĐỒNG HÀNH", font=("Arial", 28, "bold"), text_color="white", bg_color="transparent").pack(pady=20)
        
        self.scroll = ctk.CTkScrollableFrame(self, width=700, height=350, fg_color="transparent")
        self.scroll.pack()
        
        self.image_refs = []
        self.buttons = []
        self.selected_path = None

        if os.path.exists("assets"):
            files = [f for f in os.listdir("assets") if f.endswith(('.png', '.jpg', '.jpeg'))]
            COLUMNS = 3 
            for i, f in enumerate(files):
                path = os.path.join("assets", f)
                try:
                    pil_img = Image.open(path)
                    ctk_img = ctk.CTkImage(light_image=pil_img, size=(130, 130))
                    self.image_refs.append(ctk_img)
                    btn = ctk.CTkButton(self.scroll, text=f.split('.')[0], image=ctk_img, compound="top",
                        width=160, height=180, fg_color="white", text_color="black", font=("Arial", 14, "bold"),
                        command=lambda p=path, idx=i: self.select(p, idx))
                    row = i // COLUMNS
                    col = i % COLUMNS
                    btn.grid(row=row, column=col, padx=15, pady=15)
                    self.buttons.append(btn)
                except: pass

        ctk.CTkLabel(self, text="Đặt tên cho bạn mới:", font=("Arial", 16), text_color="white", bg_color="transparent").pack(pady=(10,0))
        self.name_entry = ctk.CTkEntry(self, width=300, height=40, font=("Arial", 16))
        self.name_entry.pack(pady=10)
        
        self.btn_done = ctk.CTkButton(self, text="✅ XONG RỒI", font=("Arial", 20, "bold"), height=50, width=200, fg_color="#2ecc71", hover_color="#27ae60", command=self.finish)
        self.btn_done.pack(pady=20)
        
    def select(self, path, index):
        self.selected_path = path
        for i, btn in enumerate(self.buttons):
            if i == index: btn.configure(fg_color="#f1c40f", border_width=3, border_color="white")
            else: btn.configure(fg_color="white", border_width=0)

    def finish(self):
        name = self.name_entry.get().strip()
        if not self.selected_path or not name:
            messagebox.showwarning("Thiếu thông tin", "Hãy chọn hình và đặt tên nhé!")
            return
        uid = self.controller.current_user[0]
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM companions WHERE user_id=?", (uid,))
        c.execute("INSERT INTO companions (user_id, name, avatar_path) VALUES (?,?,?)", (uid, name, self.selected_path))
        conn.commit()
        conn.close()
        self.controller.show_frame("ElderHome")

# --- MÀN HÌNH CHÍNH NGƯỜI LỚN TUỔI ---
class ElderHome(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, "#84fab0", "#8fd3f4")
        self.controller = controller
        
        self.btn_logout = ctk.CTkButton(self, text="🚪 Đăng xuất", width=100, fg_color="#e74c3c", 
                                        command=lambda: controller.show_frame("AuthFrame"))
        self.btn_logout.place(relx=0.9, rely=0.05, anchor="ne")

        self.avt_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.avt_frame.pack(pady=20)
        self.avt_lbl = ctk.CTkLabel(self.avt_frame, text="")
        self.avt_lbl.pack()
        self.name_lbl = ctk.CTkLabel(self.avt_frame, text="", font=("Arial", 20, "bold"), text_color="white")
        self.name_lbl.pack()
        
        self.bubble = ctk.CTkLabel(self, text="...", font=("Arial", 22), width=700, height=100, 
                                   fg_color="white", text_color="#333", corner_radius=20, wraplength=650)
        self.bubble.pack(pady=10)
        
        self.btn_mic = ctk.CTkButton(self, text="🎤 Bấm để nói chuyện", font=("Arial", 18), height=50, 
                                     fg_color="#ff758c", command=self.start_listening)
        self.btn_mic.pack(pady=10)
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)
        moods = [("😄 Vui", 4), ("😐 Bình thường", 3), ("😔 Buồn", 2), ("😡 Giận", 1)]
        for txt, val in moods:
            ctk.CTkButton(btn_frame, text=txt, width=100, height=50, 
                          command=lambda v=val, t=txt: self.log_mood(v, t)).pack(side="left", padx=5)

        ctk.CTkButton(self, text="📜 Xem nhật ký trò chuyện", width=200, height=40, font=("Arial", 16),
                      command=lambda: controller.show_frame("HistoryFrame")).pack(side="bottom", pady=20)

    def tkraise(self, *args, **kwargs):
        super().tkraise(*args, **kwargs)
        self.load_info()

    def load_info(self):
        if not self.controller.current_user: return
        uid = self.controller.current_user[0]
        term = self.controller.current_user[6]
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM companions WHERE user_id=?", (uid,))
        comp = c.fetchone()
        conn.close()
        if comp:
            img = ctk.CTkImage(Image.open(comp[2]), size=(180, 180))
            self.avt_lbl.configure(image=img)
            self.name_lbl.configure(text=comp[1])
            greeting = f"Chào {term}! Hôm nay {term} thế nào?"
            self.bubble.configure(text=greeting)
            speak_ai(greeting)

    def start_listening(self):
        self.btn_mic.configure(text="Đang nghe...", state="disabled", fg_color="gray")
        threading.Thread(target=self.process_voice).start()
        
    def process_voice(self):
        text = listen_mic()
        self.btn_mic.configure(text="🎤 Bấm để nói chuyện", state="normal", fg_color="#ff758c")
        if text:
            self.bubble.configure(text=f"Bác nói: {text}")
            response = "Dạ, cháu nghe rồi ạ."
            if "buồn" in text.lower(): response = "Bác đừng buồn nhé, có cháu ở đây rồi."
            elif "vui" in text.lower(): response = "Nghe bác vui cháu cũng vui lây!"
            elif "mệt" in text.lower(): response = "Bác nhớ nghỉ ngơi nhé."
            
            self.save_log(3, "Chat", f"User: {text} | AI: {response}")
            time.sleep(1)
            self.bubble.configure(text=response)
            speak_ai(response)
        else:
            self.bubble.configure(text="Cháu chưa nghe rõ ạ.")
            speak_ai("Cháu chưa nghe rõ, bác nói lại nhé.")

    def log_mood(self, val, txt):
        term = self.controller.current_user[6]
        resps = {4: "Tuyệt quá!", 3: "Bình yên là nhất ạ.", 2: "Đừng buồn bác nhé.", 1: "Bác bình tĩnh nhé."}
        r = resps.get(val, "")
        self.bubble.configure(text=r)
        speak_ai(r)
        self.save_log(val, txt.split(' ')[1], "Check-in cảm xúc")

    def save_log(self, score, label, content):
        uid = self.controller.current_user[0]
        # Lưu cả định dạng ngày (để hiển thị) và timestamp (để sắp xếp/vẽ biểu đồ)
        date_str = datetime.datetime.now().strftime("%d/%m\n%H:%M") 
        timestamp = time.time()
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO logs (user_id, date_str, timestamp, mood_score, mood_label, chat_content) VALUES (?,?,?,?,?,?)",
                  (uid, date_str, timestamp, score, label, content))
        conn.commit()
        conn.close()

# --- MÀN HÌNH LỊCH SỬ ---
class HistoryFrame(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, "#a8edea", "#fed6e3")
        self.controller = controller
        
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkButton(header, text="⬅ Quay lại", width=100, fg_color="gray",
                      command=lambda: controller.show_frame("ElderHome")).pack(side="left")
        
        ctk.CTkLabel(header, text="NHẬT KÝ TRÒ CHUYỆN", font=("Arial", 22, "bold"), text_color="#333").pack(side="left", padx=50)

        ctk.CTkButton(header, text="Đăng xuất", width=80, fg_color="#e74c3c",
                      command=lambda: controller.show_frame("AuthFrame")).pack(side="right")

        self.txt_log = ctk.CTkTextbox(self, width=800, height=450, font=("Arial", 16))
        self.txt_log.pack(pady=10)

    def tkraise(self, *args, **kwargs):
        super().tkraise(*args, **kwargs)
        self.load_logs()

    def load_logs(self):
        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        
        if not self.controller.current_user: return
        uid = self.controller.current_user[0]
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT date_str, mood_label, chat_content FROM logs WHERE user_id=? ORDER BY id DESC", (uid,))
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            self.txt_log.insert("end", "Chưa có nhật ký nào...")
        else:
            for row in rows:
                date, mood, content = row
                date_clean = date.replace('\n', ' ')
                display_text = f"⏰ [{date_clean}]\n"
                if mood == "Chat":
                    parts = content.split(" | ")
                    if len(parts) >= 2:
                        user_say = parts[0].replace("User:", "🗣 Bác:")
                        ai_say = parts[1].replace("AI:", "🤖 Bạn già:")
                        display_text += f"{user_say}\n{ai_say}\n"
                    else:
                        display_text += f"{content}\n"
                else:
                    display_text += f"😊 Cảm xúc: {mood}\n"
                
                display_text += "-"*50 + "\n"
                self.txt_log.insert("end", display_text)
                
        self.txt_log.configure(state="disabled")

# --- MÀN HÌNH NGƯỜI THÂN (ĐÃ CẢI TIẾN) ---
class RelativeHome(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, "#ffffff", "#f3f4f6")
        self.controller = controller
        
        ctk.CTkLabel(self, text="THEO DÕI SỨC KHỎE TINH THẦN", font=("Arial", 22, "bold"), text_color="#333", bg_color="transparent").pack(pady=15)
        
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20)
        
        self.chart_frame = ctk.CTkFrame(main_frame, fg_color="white")
        self.chart_frame.pack(side="left", fill="both", expand=True, padx=10)
        self.canvas = None
        
        self.advice_frame = ctk.CTkFrame(main_frame, fg_color="white", width=300)
        self.advice_frame.pack(side="right", fill="y", padx=10)
        
        ctk.CTkLabel(self.advice_frame, text="PHÂN TÍCH & LỜI KHUYÊN", font=("Arial", 16, "bold"), text_color="#d35400").pack(pady=10)
        self.txt_advice = ctk.CTkTextbox(self.advice_frame, width=280, height=400, font=("Arial", 14))
        self.txt_advice.pack(pady=5, padx=5)
        
        ctk.CTkButton(self.advice_frame, text="Cập nhật", command=self.load_data).pack(pady=10)
        ctk.CTkButton(self.advice_frame, text="Đăng xuất", fg_color="#e74c3c", command=lambda: controller.show_frame("AuthFrame")).pack(pady=10)

    def tkraise(self, *args, **kwargs):
        super().tkraise(*args, **kwargs)
        self.load_data()

    def load_data(self):
        elder_id = self.controller.current_user[8]
        if not elder_id:
            self.txt_advice.insert("1.0", "Chưa liên kết với người lớn tuổi.")
            return

        conn = get_db_connection()
        c = conn.cursor()
        # Lấy 15 dữ liệu gần nhất để vẽ biểu đồ cho rõ
        c.execute("SELECT date_str, mood_score, mood_label FROM logs WHERE user_id=? ORDER BY id DESC LIMIT 15", (elder_id,))
        logs = c.fetchall()
        c.execute("SELECT full_name, address_term FROM users WHERE id=?", (elder_id,))
        elder_info = c.fetchone()
        conn.close()
        
        if not logs:
            self.txt_advice.delete("1.0", "end")
            self.txt_advice.insert("end", "Chưa có dữ liệu.")
            return
            
        # Đảo ngược list để vẽ từ quá khứ -> hiện tại
        logs_sorted = list(reversed(logs))
        dates = [x[0] for x in logs_sorted] 
        scores = [x[1] for x in logs_sorted]
        
        # Vẽ biểu đồ
        if self.canvas: self.canvas.get_tk_widget().destroy()
        fig = Figure(figsize=(5,4), dpi=100)
        ax = fig.add_subplot(111)
        
        # Vẽ đường nối và điểm
        ax.plot(range(len(dates)), scores, marker='o', color='#8e44ad', linestyle='-', linewidth=2, markersize=8)
        
        # Thiết lập trục Y (Cảm xúc)
        ax.set_yticks([1, 2, 3, 4])
        ax.set_yticklabels(['Giận', 'Buồn', 'BT', 'Vui'])
        ax.grid(True, linestyle='--', alpha=0.6)
        
        # Thiết lập trục X (Ngày giờ) - Chỉ hiện ngày tháng cho gọn
        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels(dates, rotation=45, fontsize=8)
        
        self.canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # ================================
        # THUẬT TOÁN PHÂN TÍCH THÔNG MINH
        # ================================
        term = elder_info[1] # Cách gọi (Bác, Chú...)
        
        # 1. Tính trung bình cảm xúc
        avg = sum(scores)/len(scores)
        
        # 2. Phân tích xu hướng (5 lần gần nhất)
        recent_scores = scores[-5:] # Lấy 5 lần cuối
        trend = ""
        if len(recent_scores) >= 2:
            if recent_scores[-1] > recent_scores[0]: trend = "↗ Đang cải thiện"
            elif recent_scores[-1] < recent_scores[0]: trend = "↘ Đang đi xuống"
            else: trend = "➡ Ổn định"
        
        # 3. Tạo lời khuyên cụ thể
        advice_text = f"Báo cáo về: {elder_info[0]}\n"
        advice_text += f"Xu hướng: {trend}\n"
        advice_text += "-"*30 + "\n\n"
        
        if avg < 2.2:
            advice_text += f"⚠ CẢNH BÁO: TÂM TRẠNG KÉM\n"
            advice_text += f"{term} thường xuyên buồn hoặc tiêu cực gần đây.\n\n"
            advice_text += "👉 HÀNH ĐỘNG GỢI Ý:\n"
            advice_text += "- Hãy gọi điện video ngay (đừng chỉ nhắn tin).\n"
            advice_text += "- Gửi ảnh cháu chắt để {term} vui.\n"
            advice_text += "- Lên kế hoạch về thăm sớm nhất có thể."
        elif avg > 3.4:
            advice_text += f"✅ TÍCH CỰC: TÂM TRẠNG TỐT\n"
            advice_text += f"{term} đang rất yêu đời và vui vẻ.\n\n"
            advice_text += "👉 HÀNH ĐỘNG GỢI Ý:\n"
            advice_text += "- Khen ngợi tinh thần của {term}.\n"
            advice_text += "- Khuyến khích {term} tiếp tục các thói quen hiện tại."
        else:
            advice_text += f"⚖ BÌNH THƯỜNG: ỔN ĐỊNH\n"
            advice_text += f"Tâm trạng {term} không có nhiều biến động.\n\n"
            advice_text += "👉 HÀNH ĐỘNG GỢI Ý:\n"
            advice_text += "- Duy trì hỏi thăm đều đặn.\n"
            advice_text += "- Hỏi ý kiến {term} về các chuyện trong nhà để {term} thấy mình quan trọng."

        # Cập nhật vào Textbox
        self.txt_advice.configure(state="normal")
        self.txt_advice.delete("1.0", "end")
        self.txt_advice.insert("end", advice_text)
        self.txt_advice.configure(state="disabled")

# --- MAIN CONTROLLER ---
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Trợ lý ảo cho Người Cao Tuổi")
        self.geometry("1100x700")
        self.current_user = None
        
        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True)
        
        self.frames = {}
        for F in (AuthFrame, SetupCompanion, ElderHome, HistoryFrame, RelativeHome):
            name = F.__name__
            frame = F(parent=container, controller=self)
            self.frames[name] = frame
            frame.grid(row=0, column=0, sticky="nsew")
            
        self.show_frame("AuthFrame")
        
    def show_frame(self, name):
        frame = self.frames[name]
        frame.tkraise()

if __name__ == "__main__":
    ctk.set_appearance_mode("Light")
    app = App()
    app.mainloop()
