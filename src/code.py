import time
import random
import board
import busio
import displayio
import terminalio
import digitalio

from adafruit_display_text import label
import i2cdisplaybus
import adafruit_displayio_ssd1306
from rotary_encoder import RotaryEncoder

# =========================
# CONFIG
# =========================
MAX_LEVELS = 10
MAX_LIVES = 3

DIFFICULTIES = ["Easy", "Medium", "Hard"]
TIME_LIMITS = {
    "Easy": 8.0,   # 更宽松一点
    "Medium": 5.0,
    "Hard": 3.0,
}

MOVE_NAMES = ["CLICK", "HOLD", "TURN L", "TURN R"]
MOVE_CLICK = 0
MOVE_HOLD = 1
MOVE_LEFT = 2
MOVE_RIGHT = 3

HOLD_TIME = 1.0  # seconds to count as HOLD

# =========================
# DISPLAY
# =========================
displayio.release_displays()

i2c = busio.I2C(board.SCL, board.SDA)
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)

display = adafruit_displayio_ssd1306.SSD1306(
    display_bus,
    width=128,
    height=64
)

root = displayio.Group()
display.root_group = root

def show(lines):
    # 清空屏幕（不能用 root[:]）
    while len(root) > 0:
        root.pop()

    y = 8
    for line in lines:
        root.append(label.Label(terminalio.FONT, text=line, x=0, y=y))
        y += 16
    display.refresh()

# =========================
# INPUT
# =========================
# Rotary encoder: A -> D1, B -> D2, C -> GND
encoder = RotaryEncoder(board.D1, board.D2, debounce_ms=3, pulses_per_detent=3)
last_pos = encoder.position

# Button: one leg -> D3, other leg -> GND
button = digitalio.DigitalInOut(board.D3)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.UP

def button_pressed():
    return not button.value

# =========================
# MOVE LOGIC (no flashing countdown)
# =========================
def wait_for_move(limit):
    """
    在 limit 秒内等待玩家动作。
    不刷新屏幕，只做时间判断。
    返回 MOVE_* 或 None（超时）。
    """
    start = time.monotonic()
    last = encoder.position
    pressed_at = None

    while time.monotonic() - start < limit:
        # --- 旋钮转动 ---
        if encoder.update():
            pos = encoder.position
            if pos > last:
                return MOVE_RIGHT
            if pos < last:
                return MOVE_LEFT
            last = pos

        # --- 按钮点击 / 长按 ---
        if button_pressed() and pressed_at is None:
            pressed_at = time.monotonic()

        if (not button_pressed()) and (pressed_at is not None):
            duration = time.monotonic() - pressed_at
            pressed_at = None
            if duration >= HOLD_TIME:
                return MOVE_HOLD
            else:
                return MOVE_CLICK

        time.sleep(0.01)

    return None  # timeout

# =========================
# MAIN GAME LOOP
# =========================
difficulty_index = 0

while True:
    # -------- MENU（这里才能换难度）--------
    show([
        "Simple Game+",
        f"Diff: {DIFFICULTIES[difficulty_index]}",
        "Turn = change",
        "Press = start",
    ])

    while True:
        # 和你测试旋钮那段一样：encoder.update() + encoder.position
        if encoder.update():
            pos = encoder.position
            if pos > last_pos:
                difficulty_index = (difficulty_index + 1) % len(DIFFICULTIES)
            elif pos < last_pos:
                difficulty_index = (difficulty_index - 1) % len(DIFFICULTIES)
            last_pos = pos

            show([
                "Simple Game+",
                f"Diff: {DIFFICULTIES[difficulty_index]}",
                "Turn = change",
                "Press = start",
            ])

        if button_pressed():
            while button_pressed():
                pass
            break

        time.sleep(0.01)

    # -------- INIT GAME STATE --------
    level = 1
    lives = MAX_LIVES
    score = 0

    show([
        f"Starting: {DIFFICULTIES[difficulty_index]}",
        f"Lives: {lives}",
        "Get ready...",
        "",
    ])
    time.sleep(1.5)

    # -------- GAME LOOP --------
    while True:
        diff = DIFFICULTIES[difficulty_index]
        base_limit = TIME_LIMITS[diff]
        # 时间可以稍微随关数变短，但不低于 1.5s
        limit = max(1.5, base_limit - (level - 1) * 0.2)

        target = random.randint(0, 3)  # 0..3 对应 4 种动作

        # 只在关卡开始时画一屏，不反复刷
        show([
            f"Lvl {level}  S:{score}",
            f"Lives: {lives}",
            "Do: " + MOVE_NAMES[target],
            f"Time: {limit:.1f}s",
        ])

        move = wait_for_move(limit)

        if move != target:
            lives -= 1
            if lives > 0:
                show([
                    "Miss!",
                    f"Lives left: {lives}",
                    f"Score: {score}",
                    "Press to retry",
                ])
                while not button_pressed():
                    pass
                while button_pressed():
                    pass
                # 同一关重来
                continue
            else:
                # GAME OVER
                show([
                    "GAME OVER",
                    f"Level: {level}",
                    f"Score: {score}",
                    "Press to menu",
                ])
                while not button_pressed():
                    pass
                while button_pressed():
                    pass
                break

        # 做对了
        score += 10 * level
        level += 1

        if level > MAX_LEVELS:
            show([
                "YOU WIN!",
                f"Score: {score}",
                f"Max lvl: {MAX_LEVELS}",
                "Press to menu",
            ])
            while not button_pressed():
                pass
            while button_pressed():
                pass
            break
