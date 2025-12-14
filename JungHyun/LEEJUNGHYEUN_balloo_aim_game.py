from tkinter import *
import time
import random

import pygame


# -----------------------------
# Sound
# -----------------------------
class SoundManager:
    def __init__(self):
        pygame.mixer.init()
        self.sfx = {}

    def load_sfx(self, name: str, path: str, volume: float = 0.8):
        s = pygame.mixer.Sound(path)
        s.set_volume(volume)
        self.sfx[name] = s

    def play_sfx(self, name: str):
        s = self.sfx.get(name)
        if s:
            s.play()


# -----------------------------
# Menu Canvas (SceneChange 이용)
# -----------------------------
class MenuCanvas:
    def __init__(self, window):
        self.window = window
        self.canvas = Canvas(window, bg="white", highlightthickness=0)
        self.canvas.create_text(320, 110, font="Times 22 bold", text="Balloon Aim Game")
        self.canvas.create_text(320, 150, font="Times 12", text="Drag the aim. Release to pop a balloon.")
        self.canvas.create_text(320, 170, font="Times 12", text="ESC: back to menu")

        self.canvas.create_text(320, 240, font="Times 16 italic bold", text="Start", tags="start")
        self.canvas.create_text(320, 290, font="Times 16 italic bold", text="Exit", tags="exit")

        self.canvas.tag_bind("start", "<Button-1>", lambda e: self.window.event_generate("<<MENU_START>>"))
        self.canvas.tag_bind("exit", "<Button-1>", lambda e: self.window.event_generate("<<MENU_EXIT>>"))

    def pack(self):
        self.canvas.pack(expand=True, fill=BOTH)

    def unpack(self):
        self.canvas.pack_forget()

    def display(self):
        pass

    def destroy(self):
        self.canvas.destroy()


# -----------------------------
# Game Canvas
# DragItems_advanced: 드래그 이용
# FindWithTag / RemoveItems: 태그로 찾기/삭제 이용
# -----------------------------
class GameCanvas:
    def __init__(self, window, sound: SoundManager):
        self.window = window
        self.sound = sound

        self.w = 640
        self.h = 480
        self.canvas = Canvas(window, bg="skyblue", highlightthickness=0, width=self.w, height=self.h)

        # -------------------------
        # 이미지 로딩 (PIL 없이 PhotoImage만)
        # -------------------------
        # balloon.png, boom.png, aim.png
        self.balloon_img = PhotoImage(file="balloon.png").subsample(10, 10)
        self.aim_img = PhotoImage(file="aim.png").subsample(15, 15)
        self.aim_click_img = PhotoImage(file="boom.png").subsample(15, 15)
        #조준시 이미지 변경
        self.boom_base = PhotoImage(file="boom.png").subsample(15, 15)

        # boom 애니메이션 프레임 (zoom/subsample 사용)
        # 총 2초 동안 확대/축소가 보이도록 10프레임(200ms*10=2s) 구성
        self.boom_frames = self._make_boom_frames()

        # -------------------------
        # UI
        # -------------------------
        self.score = 0
        self.time_limit = 30.0
        self.start_time = None
        self.running = False

        self.score_text = self.canvas.create_text(10, 10, anchor="nw", fill="white",
                                                  font="Times 14 bold", text="Score: 0")
        self.time_text = self.canvas.create_text(10, 30, anchor="nw", fill="white",
                                                 font="Times 12", text="Time: 30.0")

        # -------------------------
        # 조준점(aim) - 드래그 가능
        # -------------------------
        self.aim_item = self.canvas.create_image(self.w // 2, self.h // 2, image=self.aim_img, anchor="center", tags=("aim",))

        #조준이미지 커서와 동일하게
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<Button-1>" , self._on_mouse_click) # 👈 클릭 순간
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_release)

        
        self.dragging = False
        self.drag_dx = 0
        self.drag_dy = 0

        # -------------------------
        # 풍선 관리
        # -------------------------
        self.balloons = {} 
        self.spawn_interval = 900
        self.last_spawn_ms = 0

        
    
    def _on_mouse_move(self, event):
        if not self.running:
            return

        x = max(0, min(self.w, event.x))
        y = max(0, min(self.h, event.y))
        self.canvas.coords(self.aim_item, x, y)
        self.canvas.tag_raise("aim")

  
    def _on_mouse_click(self, event):
        if not self.running:
            return

        # 클릭 순간 판정
        ax, ay = self.canvas.coords(self.aim_item)
        hit = self._find_balloon_at(ax, ay)
        if hit is not None:
            self.canvas.itemconfig(self.aim_item, image=self.aim_click_img)
            self._pop_balloon(hit)

    # 클릭 순간 조준 이미지 변경
        self.canvas.itemconfig(self.aim_item, image=self.aim_click_img)



    def _on_mouse_release(self, event):
        if not self.running:
            return

        # 다시 기본 조준 이미지로 복귀
        self.canvas.itemconfig(self.aim_item, image=self.aim_img)


      

    def _make_boom_frames(self):
        base = self.boom_base

        # 작은 크기
        f_sub3 = base.subsample(3, 3)
        f_sub2 = base.subsample(2, 2)
        f_1 = base  # 원본

        # 큰 크기
        f_z2 = base.zoom(2, 2)
        f_z3 = base.zoom(3, 3)

        # 10 프레임: 확대 → 축소 (총 2초)
        frames = [f_sub3, f_sub2, f_1, f_z2, f_z3, f_z2, f_1, f_sub2, f_sub3, f_sub2]
        return frames

    def pack(self):
        self.canvas.pack(expand=True, fill=BOTH)
        self.canvas.config(cursor="none")

    def unpack(self):
        self.canvas.pack_forget()

    def start(self):
        self.running = True
        self.score = 0
        self.start_time = time.time()
        self.last_spawn_ms = 0
        self._clear_balloons()
        self._update_hud()

    def stop(self):
        self.running = False
        self.dragging = False

    def _clear_balloons(self):
        for item_id in list(self.balloons.keys()):
            try:
                self.canvas.delete(item_id)
            except Exception:
                pass
        self.balloons.clear()

    def _update_hud(self):
        remain = self.time_limit
        if self.start_time is not None:
            remain = max(0.0, self.time_limit - (time.time() - self.start_time))
        self.canvas.itemconfig(self.score_text, text=f"Score: {self.score}")
        self.canvas.itemconfig(self.time_text, text=f"Time: {remain:0.1f}")

    # -------------------------
    # Drag handlers
    # -------------------------
    def _on_aim_press(self, event):
        if not self.running:
            return
        self.dragging = True
        x0, y0 = self.canvas.coords(self.aim_item)
        self.drag_dx = x0 - event.x
        self.drag_dy = y0 - event.y

    def _on_aim_motion(self, event):
        if not (self.running and self.dragging):
            return
        nx = event.x + self.drag_dx
        ny = event.y + self.drag_dy
        nx = max(0, min(self.w, nx))
        ny = max(0, min(self.h, ny))
        self.canvas.coords(self.aim_item, nx, ny)

    def _on_aim_release(self, event):
        if not self.running:
            return
        self.dragging = False

        ax, ay = self.canvas.coords(self.aim_item)
        hit = self._find_balloon_at(ax, ay)
        if hit is not None:
            self._pop_balloon(hit)

    # -------------------------
    # Balloon logic
    # -------------------------
    def _spawn_balloon(self):
        
        bw = self.balloon_img.width()
        bh = self.balloon_img.height()
        margin_x = bw // 2 + 10
        margin_y = bh // 2 + 50

        if margin_x >= self.w - margin_x or margin_y >= self.h - margin_y:
            x = self.w //2
            y = self.h //2
        else :
            x = random.randint(margin_x, self.w - margin_x)
            y = random.randint(margin_y, self.h - margin_y)

        item = self.canvas.create_image(
            x, y, 
            image=self.balloon_img, 
            anchor="center", 
            tags=("balloon",)
        )
        self.balloons[item] = {"x": x, "y": y}

        self.canvas.tag_raise("aim") #풍선 생성할 때 조준점이 가려지지 않게 해줌

    def _find_balloon_at(self, x, y):
        items = self.canvas.find_overlapping(x, y, x, y)
        for it in items:
            if "balloon" in self.canvas.gettags(it):
                return it
        return None

    def _pop_balloon(self, balloon_item):
        info = self.balloons.get(balloon_item)
        if not info:
            return

        try:
            self.canvas.delete(balloon_item)
        except Exception:
            pass
        self.balloons.pop(balloon_item, None)

        self.score += 1
        self._update_hud()

        # boom 확대/축소 애니메이션 (2초)
        self._boom_animation(info["x"], info["y"], frame_idx=0, boom_item=None)

    def _boom_animation(self, x, y, frame_idx, boom_item):
        # 10 프레임 * 200ms = 2초
        if frame_idx == 0:
            boom_item = self.canvas.create_image(x, y, image=self.boom_frames[0], anchor="center", tags=("boom",))
        else:
            self.canvas.itemconfig(boom_item, image=self.boom_frames[frame_idx])

        if frame_idx >= len(self.boom_frames) - 1:
            self.canvas.after(200, lambda: self.canvas.delete(boom_item))
            return

        self.canvas.after(200, lambda: self._boom_animation(x, y, frame_idx + 1, boom_item))

    # -------------------------
    # Frame update
    # -------------------------
    def update(self):
        if not self.running:
            return

        elapsed = time.time() - self.start_time
        remain = self.time_limit - elapsed
        if remain <= 0:
            self.running = False
            self._update_hud()
            self.canvas.create_text(self.w // 2, self.h // 2,
                                    fill="white", font="Times 22 bold",
                                    text=f"Time Over!\nScore: {self.score}")
            return

        # 랜덤 풍선 생성
        ms = int(elapsed * 1000)
        if ms - self.last_spawn_ms >= self.spawn_interval:
            self.last_spawn_ms = ms
            self._spawn_balloon()

        self._update_hud()

    def display(self):
        self.update()

    def destroy(self):
        self.canvas.destroy()


# -----------------------------
# Scene Controller (SceneChange 이용)
# -----------------------------
class SceneChange:
    def __init__(self):
        self.window = Tk()
        self.window.title("JungHyun WWWW - Balloon Aim Game")
        self.window.geometry("640x480")
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.sound = SoundManager()

        pygame.mixer.music.load("music.wav")
        pygame.mixer.music.set_volume(0.3)
        

        self.scene_idx = 0  # 0: menu, 1: game
        self.menu = MenuCanvas(self.window)
        self.game = GameCanvas(self.window, self.sound)

        self.canvas_list = [self.menu, self.game]
        self.menu.pack()

        self.window.bind("<<MENU_START>>", self.on_menu_start)
        self.window.bind("<<MENU_EXIT>>", self.on_menu_exit)
        self.window.bind("<KeyPress>", self.on_key_press)

        self.tick()

    def tick(self):
        try:
            for c in self.canvas_list:
                c.display()
        except TclError:
            return
        self.window.after(16, self.tick)

    def on_menu_start(self, _event=None):
        if self.scene_idx != 0:
            return
        self.scene_idx = 1
        self.menu.unpack()
        self.game.pack()
        self.game.start()

        pygame.mixer.music.play(-1) #start 누르면 music 시작

    def on_menu_exit(self, _event=None):
        self.on_closing()

    def on_key_press(self, event):
        if event.keysym == "Escape":
            if self.scene_idx == 1:
                pygame.mixer.music.stop() # 메뉴로 돌아가면 음악 정지
                self.scene_idx = 0
                self.game.stop()
                self.game.unpack()
                self.menu.pack()

    def on_closing(self):
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        for c in self.canvas_list:
            try:
                c.destroy()
            except Exception:
                pass
        try:
            self.window.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    app = SceneChange()
    app.window.mainloop()
