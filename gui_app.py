import customtkinter as ctk
import threading
import asyncio
import logging
from typing import List, Dict, Any
import sys
import os
import requests
import webbrowser

# --- إعدادات التحديث التلقائي ---
# مكتبات Velopack
from velopack import UpdateManager, VelopackApp

# ضع هنا رابط مستودع GitHub (يجب أن يكون Public)
# مثال: "https://github.com/YourUsername/DiscordQuestCompleter"
UPDATE_URL = "https://github.com/moondddf/test.git"

# استدعاء الكلاسات والدوال من ملف main.py
from main import (
    QuestClient, quest_name, expired, not_started, quest_tasks, QuestError,
    task_priority, quest_app_name, quest_app_id, presence_worker, enrolled,
    wait_for_enrollment, complete_quest
)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class GUILogHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.after(0, self.append_log, msg)

    def append_log(self, msg):
        self.text_widget.configure(state="normal")
        self.text_widget.insert("end", msg + "\n")
        self.text_widget.see("end")
        self.text_widget.configure(state="disabled")

class DiscordQuestApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("مكمل مهام ديسكورد")
        self.geometry("700x750")
        self.client = None
        self.available_quests = []
        self.checkboxes = []
        self.token = ""

        self.build_main_ui()
        
        # إظهار واجهة التحميل عند بدء التشغيل
        self.show_overlay("جاري التحقق من وجود تحديثات...", show_progress=True)
        
        # تشغيل الفحص في مسار خلفي (Thread) حتى لا تتجمد الواجهة
        threading.Thread(target=self.auto_update_routine, daemon=True).start()

    def build_main_ui(self):
        # تم إزالة إعلان Gist القديم، الواجهة تبدأ مباشرة بإدخال التوكن
        self.token_frame = ctk.CTkFrame(self)
        self.token_frame.pack(pady=20, padx=20, fill="x")
        
        self.token_label = ctk.CTkLabel(self.token_frame, text="Discord Token:", font=("Arial", 14, "bold"))
        self.token_label.pack(pady=5)
        
        self.token_entry = ctk.CTkEntry(self.token_frame, placeholder_text="ضع التوكن هنا...", width=500, show="*")
        self.token_entry.pack(pady=5)
        
        self.fetch_btn = ctk.CTkButton(self.token_frame, text="تسجيل الدخول وجلب الكويستات", command=self.start_fetch_thread)
        self.fetch_btn.pack(pady=10)

        self.quests_label = ctk.CTkLabel(self, text="الكويستات المتاحة:", font=("Arial", 14, "bold"))
        self.quests_label.pack(pady=5)

        self.scrollable_frame = ctk.CTkScrollableFrame(self, width=600, height=200)
        self.scrollable_frame.pack(pady=5, padx=20, fill="both", expand=False)

        self.log_label = ctk.CTkLabel(self, text="سجل العمليات (Logs):", font=("Arial", 14, "bold"))
        self.log_label.pack(pady=(10, 0))
        
        self.log_textbox = ctk.CTkTextbox(self, width=600, height=200, state="disabled", fg_color="#1e1e1e", text_color="#00ff00")
        self.log_textbox.pack(pady=5, padx=20, fill="both", expand=True)

        self.control_frame = ctk.CTkFrame(self)
        self.control_frame.pack(pady=15, padx=20, fill="x")

        self.status_label = ctk.CTkLabel(self.control_frame, text="في انتظار التوكن...", text_color="gray")
        self.status_label.pack(side="left", padx=15)

        self.start_btn = ctk.CTkButton(self.control_frame, text="بدء إكمال المحدد", state="disabled", fg_color="green", hover_color="darkgreen", command=self.start_process_thread)
        self.start_btn.pack(side="right", padx=15)

        self.setup_logging()

    def show_overlay(self, message, show_progress=False):
        if hasattr(self, 'overlay_frame') and self.overlay_frame.winfo_exists():
            self.overlay_frame.destroy()

        self.overlay_frame = ctk.CTkFrame(self, fg_color="#121212")
        self.overlay_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.dialog_frame = ctk.CTkFrame(self.overlay_frame, fg_color="#1e1e1e", border_width=2, border_color="#3b8ed0", corner_radius=15)
        self.dialog_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.7, relheight=0.4)

        ctk.CTkLabel(self.dialog_frame, text="نظام التحديث التلقائي", font=("Arial", 20, "bold"), text_color="white").pack(pady=(25, 10))

        self.overlay_msg_label = ctk.CTkLabel(self.dialog_frame, text=message, font=("Arial", 16), wraplength=400)
        self.overlay_msg_label.pack(pady=10, padx=20)

        if show_progress:
            self.overlay_progress = ctk.CTkProgressBar(self.dialog_frame, width=300)
            self.overlay_progress.pack(pady=15)
            self.overlay_progress.set(0)

    def auto_update_routine(self):
        """دالة للتحقق من التحديثات باستخدام Velopack"""
        try:
            # تهيئة مدير التحديثات
            mgr = UpdateManager(UPDATE_URL)
            
            # فحص هل يوجد إصدار جديد؟
            update_info = mgr.check_for_updates()
            
            if update_info is None:
                # لا يوجد تحديث، البرنامج محدث لأحدث نسخة
                self.after(500, self.launch_main_app)
                return

            # يوجد تحديث، نعرض للمستخدم ونبدأ التنزيل
            self.after(0, lambda: self.overlay_msg_label.configure(text=f"تم العثور على الإصدار {update_info.version}!\nجاري التنزيل..."))

            # دالة لتحديث شريط التقدم في الواجهة
            def on_progress(percent):
                self.after(0, lambda: self.overlay_progress.set(percent / 100.0))

            # تحميل التحديث
            mgr.download_updates(update_info, progress_callback=on_progress)
            
            self.after(0, lambda: self.overlay_msg_label.configure(text="اكتمل التنزيل! جاري إعادة تشغيل البرنامج..."))
            
            # تطبيق التحديث وإعادة تشغيل البرنامج تلقائياً
            mgr.apply_updates_and_restart(update_info)

        except Exception as e:
            # في حال فشل الاتصال بالإنترنت أو عدم صحة الرابط
            self.logger.error(f"فشل التحقق من التحديثات: {e}")
            self.after(0, lambda: self.overlay_msg_label.configure(text="تعذر فحص التحديثات. جاري الدخول للبرنامج..."))
            self.after(2000, self.launch_main_app)

    def launch_main_app(self):
        if hasattr(self, 'overlay_frame') and self.overlay_frame.winfo_exists():
            self.overlay_frame.destroy()
        
        # جلب رقم الإصدار الحالي لعرضه في العنوان (يعمل تلقائياً عند تحزيم البرنامج)
        try:
            mgr = UpdateManager(UPDATE_URL)
            current_version = mgr.get_current_version()
            if current_version:
                self.title(f"مكمل مهام ديسكورد - الإصدار {current_version}")
        except:
            pass

    # بقية الدوال (setup_logging, update_status, start_fetch_thread, run_async_fetch, fetch_quests, display_quests, start_process_thread, run_async_process, enable_checkboxes, process_quests) تبقى كما هي بدون أي تغيير!
    def setup_logging(self):
        main_logger = logging.getLogger("quest-completer")
        main_logger.setLevel(logging.INFO)
        for handler in main_logger.handlers[:]:
            main_logger.removeHandler(handler)
        gui_handler = GUILogHandler(self.log_textbox)
        formatter = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S")
        gui_handler.setFormatter(formatter)
        main_logger.addHandler(gui_handler)
        self.logger = main_logger

    def update_status(self, text, color="white"):
        self.status_label.configure(text=text, text_color=color)

    def start_fetch_thread(self):
        self.token = self.token_entry.get().strip()
        if not self.token:
            self.update_status("الرجاء إدخال التوكن أولاً!", "red")
            return

        self.update_status("جاري الاتصال وجلب المهام...", "yellow")
        self.fetch_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        
        threading.Thread(target=self.run_async_fetch, daemon=True).start()

    def run_async_fetch(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.fetch_quests())
        except Exception as e:
            self.update_status(f"خطأ غير متوقع: {e}", "red")
            self.fetch_btn.configure(state="normal")
        finally:
            loop.close()

    async def fetch_quests(self):
        self.client = QuestClient(self.token)
        try:
            user = await asyncio.to_thread(self.client.me)
            quests = await asyncio.to_thread(self.client.quests)
            
            active_quests = [q for q in quests if not expired(q) and not not_started(q)]
            self.available_quests = active_quests

            if not active_quests:
                self.update_status(f"تم الدخول كـ {user['username']} - لا توجد كويستات.", "orange")
            else:
                self.update_status(f"تم الدخول كـ {user['username']} - عثر على {len(active_quests)} كويست.", "green")
                self.after(0, self.display_quests)

        except QuestError as exc:
            self.update_status(f"فشل الاتصال: {exc}", "red")
        
        self.after(0, lambda: self.fetch_btn.configure(state="normal"))

    def display_quests(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.checkboxes.clear()

        for quest in self.available_quests:
            name = quest_name(quest)
            tasks = ", ".join(quest_tasks(quest)) or "unknown"
            
            chk_var = ctk.StringVar(value="on")
            chk = ctk.CTkCheckBox(self.scrollable_frame, text=f"{name} ({tasks})", variable=chk_var, onvalue="on", offvalue="off")
            chk.pack(pady=5, padx=10, anchor="w")
            
            self.checkboxes.append({"quest": quest, "var": chk_var})

        if self.available_quests:
            self.start_btn.configure(state="normal")

    def start_process_thread(self):
        selected_quests = [item["quest"] for item in self.checkboxes if item["var"].get() == "on"]
        if not selected_quests:
            self.update_status("الرجاء تحديد كويست واحد على الأقل!", "red")
            return

        self.update_status("جاري تنفيذ المهام المحددة...", "yellow")
        self.fetch_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        
        for item in self.checkboxes:
            item["var"].set(item["var"].get())
            for widget in self.scrollable_frame.winfo_children():
                widget.configure(state="disabled")

        self.logger.info(f"بدء إكمال {len(selected_quests)} مهمة(مهام)...")
        threading.Thread(target=self.run_async_process, args=(selected_quests,), daemon=True).start()

    def run_async_process(self, selected_quests):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.process_quests(selected_quests))
            self.update_status("تم الانتهاء من معالجة الكويستات المحددة.", "green")
        except Exception as e:
            self.logger.error(f"حدث خطأ أثناء التشغيل: {e}")
            self.update_status("حدث خطأ أثناء التشغيل، راجع السجل.", "red")
        finally:
            loop.close()
            self.after(0, lambda: self.fetch_btn.configure(state="normal"))
            self.after(0, lambda: self.start_btn.configure(state="normal"))
            self.after(0, lambda: self.enable_checkboxes())

    def enable_checkboxes(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.configure(state="normal")

    async def process_quests(self, selected_quests):
        matches = sorted(selected_quests, key=task_priority)
        activity_name = quest_app_name(matches[0])
        activity: Dict[str, Any] = {"name": activity_name, "type": 0}
        app_id = quest_app_id(matches[0])
        if app_id:
            activity["application_id"] = app_id

        stop_presence = asyncio.Event()
        presence_task = asyncio.create_task(presence_worker(self.token, activity, "online", stop_presence))

        try:
            for quest in matches:
                if not enrolled(quest):
                    try:
                        quest["user_status"] = await asyncio.to_thread(self.client.enroll, quest["id"], quest)
                        self.logger.info("Accepted quest: %s", quest_name(quest))
                    except QuestError as exc:
                        self.logger.warning("Could not auto-accept '%s': %s", quest_name(quest), exc)
                
                if not enrolled(quest):
                    quest = await wait_for_enrollment(self.client, quest["id"])
                
                try:
                    await complete_quest(self.client, quest)
                except QuestError as exc:
                    self.logger.error("Quest completion error: %s", exc)
        finally:
            stop_presence.set()
            await presence_task
            self.logger.info("All selected quests processed.")

if __name__ == "__main__":
    # --- أمر تهيئة التحديث التلقائي ---
    # يجب أن يوضع هذا السطر قبل تشغيل الواجهة ليقوم بإدارة استبدال الملفات أثناء التحديث
    VelopackApp.build().run()
    
    app = DiscordQuestApp()
    app.mainloop()