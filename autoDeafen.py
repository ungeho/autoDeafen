import time
from typing import Optional

import requests
import urllib3
from pynput.keyboard import Key, Controller

# --- 設定 ----------------------------------------------------

ALL_GAME_DATA_URL = "https://127.0.0.1:2999/liveclientdata/allgamedata"

# ゲーム開始時に実行するコマンドを"/mute all"や"/fullmute all"に変更したい場合はここを変更する。
DEAFEN_COMMAND = "/deafen"

# GameStart から何秒後に /deafen を送るか
GAME_START_DELAY = 1.0

# ポーリング間隔（秒）
POLL_INTERVAL = 0.5

# 自己署名証明書の警告を無効化
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

keyboard = Controller()


# --- ユーティリティ ------------------------------------------


def send_chat_message(message: str) -> None:
    """
    LoLクライアントのチャットに message を送信する。
    （フォーカスされているウィンドウに対して送るので注意）
    """
    # チャットを開く
    keyboard.press(Key.enter)
    keyboard.release(Key.enter)
    time.sleep(0.05)

    # メッセージ入力
    keyboard.type(message)
    time.sleep(0.05)

    # 送信
    keyboard.press(Key.enter)
    keyboard.release(Key.enter)
    time.sleep(0.05)


def fetch_all_game_data(session: requests.Session) -> Optional[dict]:
    """
    allgamedata を取得して dict を返す。
    取得できない場合は None を返す。
    """
    try:
        r = session.get(ALL_GAME_DATA_URL, verify=False, timeout=0.5)
        if not r.ok:
            return None
        return r.json()
    except requests.exceptions.RequestException:
        return None


def find_game_start_time(events: list) -> Optional[float]:
    """
    events から GameStart イベントの EventTime を探して返す。
    見つからなければ None。
    """
    for ev in events:
        if ev.get("EventName") == "GameStart":
            try:
                return float(ev.get("EventTime", 0.0))
            except (TypeError, ValueError):
                return None
    return None


# --- メインループ --------------------------------------------


def main() -> None:
    in_game = False                 # 今ゲーム中かどうか
    deafen_sent = False             # このゲームで /deafen 済みかどうか
    game_start_time: Optional[float] = None

    # セッションを使い回して少し効率よく
    session = requests.Session()

    print("Waiting for game... (Ctrl+C で終了)")

    while True:
        data = fetch_all_game_data(session)

        if data is None:
            # ゲーム外（ロビー or 完全終了）
            if in_game:
                print("Game seems to have ended or not started yet.")
            in_game = False
            deafen_sent = False
            game_start_time = None
            time.sleep(POLL_INTERVAL)
            continue

        # ここまで来ている = ライブゲーム中
        if not in_game:
            print("Game detected via allgamedata.")
            in_game = True
            deafen_sent = False
            game_start_time = None

        events = data.get("events", {}).get("Events", [])
        try:
            game_time = float(data.get("gameData", {}).get("gameTime", 0.0))
        except (TypeError, ValueError):
            game_time = 0.0

        # GameStart がまだ記録されていなければ探す
        if game_start_time is None:
            game_start_time = find_game_start_time(events)
            if game_start_time is not None:
                print(f"GameStart event found at {game_start_time:.2f}s")

        # /deafen を送る条件：
        #  - GameStart イベントが存在している
        #  - まだ /deafen を送っていない
        #  - gameTime が GameStart + GAME_START_DELAY を超えている
        if (
            game_start_time is not None
            and not deafen_sent
            and game_time >= game_start_time + GAME_START_DELAY
        ):
            print(f"Sending /deafen at gameTime={game_time:.2f}s")
            # ★この時点で LoL クライアントがアクティブである必要あり
            send_chat_message(DEAFEN_COMMAND)
            deafen_sent = True
            print("Done. Waiting for game end...")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
