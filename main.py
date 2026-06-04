"""
Chess Trainer  —  Main Program
CS 361 Final Project

Orchestrates four microservices over gRPC. Never imports any service server
directly — all communication is through network requests and responses.

  Port 50051  Microservice A: Move Validation
  Port 50052  Microservice B: Chess Engine (best moves)
  Port 50053  Microservice C: Turn Timer
  Port 50054  Microservice D: Chat / Game Log

Run with:
    python3 main.py
"""

import grpc
import json
import sys
import os
import time

# ── Add service directories to path for stubs ─────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "services", "validation"))
sys.path.insert(0, os.path.join(BASE, "services", "engine"))
sys.path.insert(0, os.path.join(BASE, "services", "timer"))
sys.path.insert(0, os.path.join(BASE, "services", "chat"))

import chess_pb2,  chess_pb2_grpc
import engine_pb2, engine_pb2_grpc
import timer_pb2,  timer_pb2_grpc
import chat_pb2,   chat_pb2_grpc

# ── gRPC stubs (one per microservice) ─────────────────────────────────────────
val_channel    = grpc.insecure_channel("localhost:50051")
engine_channel = grpc.insecure_channel("localhost:50052")
timer_channel  = grpc.insecure_channel("localhost:50053")
chat_channel   = grpc.insecure_channel("localhost:50054")

validator = chess_pb2_grpc.MoveValidatorStub(val_channel)
engine    = engine_pb2_grpc.ChessEngineStub(engine_channel)
timer     = timer_pb2_grpc.TurnTimerStub(timer_channel)
chat      = chat_pb2_grpc.ChatServiceStub(chat_channel)

# ── Helpers ────────────────────────────────────────────────────────────────────

STARTING_BOARD = {
    "A1":"WHITE_ROOK","B1":"WHITE_KNIGHT","C1":"WHITE_BISHOP","D1":"WHITE_QUEEN",
    "E1":"WHITE_KING","F1":"WHITE_BISHOP","G1":"WHITE_KNIGHT","H1":"WHITE_ROOK",
    "A2":"WHITE_PAWN","B2":"WHITE_PAWN","C2":"WHITE_PAWN","D2":"WHITE_PAWN",
    "E2":"WHITE_PAWN","F2":"WHITE_PAWN","G2":"WHITE_PAWN","H2":"WHITE_PAWN",
    "A7":"BLACK_PAWN","B7":"BLACK_PAWN","C7":"BLACK_PAWN","D7":"BLACK_PAWN",
    "E7":"BLACK_PAWN","F7":"BLACK_PAWN","G7":"BLACK_PAWN","H7":"BLACK_PAWN",
    "A8":"BLACK_ROOK","B8":"BLACK_KNIGHT","C8":"BLACK_BISHOP","D8":"BLACK_QUEEN",
    "E8":"BLACK_KING","F8":"BLACK_BISHOP","G8":"BLACK_KNIGHT","H8":"BLACK_ROOK",
}

FILES = "ABCDEFGH"

def print_board(board):
    """Print the board as ASCII art."""
    print("\n    A  B  C  D  E  F  G  H")
    print("   ─────────────────────────")
    for rank in range(8, 0, -1):
        row = f" {rank} │"
        for f in FILES:
            sq = f"{f}{rank}"
            piece = board.get(sq, "")
            if not piece:
                row += " . "
            elif piece.startswith("WHITE"):
                symbols = {"PAWN":"♙","ROOK":"♖","KNIGHT":"♘","BISHOP":"♗","QUEEN":"♕","KING":"♔"}
                row += f" {symbols.get(piece.split('_',1)[1], '?')} "
            else:
                symbols = {"PAWN":"♟","ROOK":"♜","KNIGHT":"♞","BISHOP":"♝","QUEEN":"♛","KING":"♚"}
                row += f" {symbols.get(piece.split('_',1)[1], '?')} "
        print(row)
    print("   ─────────────────────────\n")

def check_services():
    """Verify all four microservices are reachable before starting."""
    services = [
        ("Move Validation",  "localhost:50051"),
        ("Chess Engine",     "localhost:50052"),
        ("Turn Timer",       "localhost:50053"),
        ("Chat / Game Log",  "localhost:50054"),
    ]
    all_ok = True
    print("\nChecking microservices...")
    for name, addr in services:
        try:
            ch = grpc.insecure_channel(addr)
            grpc.channel_ready_future(ch).result(timeout=2)
            print(f"  ✓ {name} ({addr})")
        except grpc.FutureTimeoutError:
            print(f"  ✗ {name} ({addr})  — NOT RUNNING")
            all_ok = False
    return all_ok

# ── Feature functions (each calls exactly one microservice) ───────────────────

def feature_validate_move(game_id, player_id, src, dst, move_type, board):
    """
    FEATURE: Move validation
    MICROSERVICE A — port 50051
    REQUEST:  ValidateMoveRequest with full board state and move details
    RECEIVE:  ValidateMoveResponse with is_valid, updated_board, check_state
    """
    print(f"\n[MS-A Move Validation] Sending request: {src}→{dst}")
    response = validator.ValidateMove(chess_pb2.ValidateMoveRequest(
        game_id        = game_id,
        player_id      = player_id,
        piece_position = src,
        target_position= dst,
        move_type      = move_type,
        board_state    = json.dumps(board),
    ))
    print(f"[MS-A Move Validation] Response: valid={response.is_valid}"
          f"  check={response.check_state}"
          f"  msg='{response.error_message}'")
    return response

def feature_get_hints(game_id, board, active_color):
    """
    FEATURE: Move hints (top 3 best moves)
    MICROSERVICE B — port 50052
    REQUEST:  BestMovesRequest with board state and active color
    RECEIVE:  BestMovesResponse with ranked SuggestedMove list
    """
    print(f"\n[MS-B Chess Engine] Requesting top 3 moves for {active_color}...")
    response = engine.GetBestMoves(engine_pb2.BestMovesRequest(
        game_id      = game_id,
        board_state  = json.dumps(board),
        active_color = active_color,
    ))
    if response.error_message:
        print(f"[MS-B Chess Engine] Error: {response.error_message}")
        return response
    for move in response.moves:
        print(f"[MS-B Chess Engine] #{move.rank} {move.piece_position}→{move.target_position}"
              f"  score={move.score}  | {move.reasoning}")
    return response

def feature_start_timer(game_id, color):
    """
    FEATURE: Start turn timer
    MICROSERVICE C — port 50053
    REQUEST:  StartTurnRequest with game_id and active color
    RECEIVE:  StartTurnResponse with seconds_remaining
    """
    print(f"\n[MS-C Timer] Starting {color}'s turn timer...")
    response = timer.StartTurn(timer_pb2.StartTurnRequest(
        game_id      = game_id,
        active_color = color,
    ))
    print(f"[MS-C Timer] Response: success={response.success}"
          f"  seconds_remaining={response.seconds_remaining}")
    return response

def feature_check_timer(game_id, color):
    """
    FEATURE: Check remaining time
    MICROSERVICE C — port 50053
    REQUEST:  CheckTimeRequest
    RECEIVE:  CheckTimeResponse with seconds_remaining and time_expired flag
    """
    response = timer.CheckTime(timer_pb2.CheckTimeRequest(
        game_id      = game_id,
        active_color = color,
    ))
    print(f"[MS-C Timer] {color} has {response.seconds_remaining}s remaining"
          f"  expired={response.time_expired}")
    return response

def feature_end_timer(game_id, color):
    """
    FEATURE: End turn timer, deduct time used
    MICROSERVICE C — port 50053
    REQUEST:  EndTurnRequest
    RECEIVE:  EndTurnResponse with seconds_used and seconds_remaining
    """
    response = timer.EndTurn(timer_pb2.EndTurnRequest(
        game_id      = game_id,
        active_color = color,
    ))
    print(f"[MS-C Timer] {color} used {response.seconds_used}s,"
          f" {response.seconds_remaining}s remaining in bank")
    return response

def feature_log_event(game_id, event_type, description):
    """
    FEATURE: Log a game event
    MICROSERVICE D — port 50054
    REQUEST:  LogEventRequest with event type and description
    RECEIVE:  LogEventResponse with timestamp
    """
    response = chat.LogGameEvent(chat_pb2.LogEventRequest(
        game_id     = game_id,
        event_type  = event_type,
        description = description,
    ))
    print(f"[MS-D Chat] Event logged at {response.timestamp}: {description}")
    return response

def feature_post_chat(game_id, player_id, message):
    """
    FEATURE: Post a chat message
    MICROSERVICE D — port 50054
    REQUEST:  PostMessageRequest with player_id and message text
    RECEIVE:  PostMessageResponse with timestamp
    """
    response = chat.PostMessage(chat_pb2.PostMessageRequest(
        game_id   = game_id,
        player_id = player_id,
        message   = message,
    ))
    print(f"[MS-D Chat] Message stored at {response.timestamp}")
    return response

def feature_get_chat(game_id, limit=0):
    """
    FEATURE: Retrieve chat and event log
    MICROSERVICE D — port 50054
    REQUEST:  GetMessagesRequest
    RECEIVE:  GetMessagesResponse with list of ChatEntry objects
    """
    response = chat.GetMessages(chat_pb2.GetMessagesRequest(
        game_id = game_id,
        limit   = limit,
    ))
    return response.entries

def feature_export_log(game_id):
    """
    FEATURE: Export full annotated game log
    MICROSERVICE D — port 50054
    REQUEST:  ExportLogRequest
    RECEIVE:  ExportLogResponse with full plain-text log
    """
    response = chat.ExportLog(chat_pb2.ExportLogRequest(game_id=game_id))
    return response.full_log

# ── Interactive game loop ──────────────────────────────────────────────────────

def run_game():
    game_id   = f"game_{int(time.time())}"
    board     = dict(STARTING_BOARD)
    turn      = "WHITE"
    move_num  = 1
    hints_on  = True

    print("\n" + "=" * 58)
    print("        Chess Trainer  —  CS 361 Final Project")
    print("=" * 58)
    print(f"  Game ID : {game_id}")
    print("  Four microservices active on ports 50051–50054")
    print("=" * 58)

    # Configure timer — Microservice C
    seconds = 300
    try:
        custom = input("\nSeconds per player (default 300, press Enter to skip): ").strip()
        if custom.isdigit():
            seconds = int(custom)
    except (EOFError, KeyboardInterrupt):
        pass

    print(f"\n[MS-C Timer] Configuring {seconds}s per player...")
    timer.ConfigTimer(timer_pb2.ConfigTimerRequest(
        game_id=game_id, seconds_per_player=seconds
    ))

    # Log game start — Microservice D
    feature_log_event(game_id, "GAME_START", f"Game started. {seconds}s per player.")

    print("\nCommands:  <FROM> <TO>  (e.g. E2 E4)  |  hint  |  chat <msg>  |  log  |  quit")

    while True:
        print_board(board)
        print(f"  Move {move_num} — {turn}'s turn")

        # Start turn timer — Microservice C
        feature_start_timer(game_id, turn)

        # Get hints — Microservice B
        if hints_on:
            hints_resp = feature_get_hints(game_id, board, turn)
            if hints_resp.moves:
                print("\n  Suggested moves:")
                for m in hints_resp.moves:
                    print(f"    #{m.rank}  {m.piece_position}→{m.target_position}  — {m.reasoning}")

        # Check time — Microservice C
        time_resp = feature_check_timer(game_id, turn)
        mins, secs = divmod(time_resp.seconds_remaining, 60)
        print(f"\n  Time remaining: {mins}m {secs:02d}s")

        if time_resp.time_expired:
            print(f"\n  ⏰ {turn}'s time has expired! Game over.")
            feature_log_event(game_id, "FORFEIT", f"{turn} ran out of time.")
            break

        # Player input
        try:
            raw = input(f"\n  {turn} > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not raw:
            continue

        # ── quit ──
        if raw.lower() == "quit":
            feature_log_event(game_id, "GAME_END", "Game ended by player.")
            break

        # ── log ──
        if raw.lower() == "log":
            feature_end_timer(game_id, turn)
            feature_start_timer(game_id, turn)  # resume
            print("\n" + feature_export_log(game_id))
            continue

        # ── chat <message> ──
        if raw.lower().startswith("chat "):
            msg = raw[5:].strip()
            if msg:
                feature_post_chat(game_id, turn, msg)
                entries = feature_get_chat(game_id, limit=5)
                print("\n  Recent chat:")
                for e in entries:
                    icon = "♟" if e.entry_type == "EVENT" else "💬"
                    print(f"    [{e.timestamp}] {icon} {e.player_id}: {e.message}")
            continue

        # ── hints toggle ──
        if raw.lower() == "hint":
            hints_on = not hints_on
            print(f"  Hints {'ON' if hints_on else 'OFF'}")
            continue

        # ── move input ──
        parts = raw.upper().split()
        if len(parts) != 2:
            print("  Usage: <FROM> <TO>  e.g.  E2 E4")
            continue

        src, dst = parts
        if len(src) != 2 or len(dst) != 2:
            print("  Squares must be like E2, D7, etc.")
            continue

        # Validate move — Microservice A
        val_resp = feature_validate_move(
            game_id, turn.lower(), src, dst, "NORMAL", board
        )

        # End timer for this turn — Microservice C
        feature_end_timer(game_id, turn)

        if not val_resp.is_valid:
            print(f"\n  ✗ Illegal move: {val_resp.error_message}")
            # Restart timer for retry
            feature_start_timer(game_id, turn)
            continue

        # Apply updated board
        board = json.loads(val_resp.updated_board)

        # Log the move — Microservice D
        piece = STARTING_BOARD.get(src, board.get(dst, "piece"))
        feature_log_event(game_id, "MOVE", f"{turn} played {src}→{dst}")

        if val_resp.check_state:
            opponent = "BLACK" if turn == "WHITE" else "WHITE"
            print(f"\n  ♚ {opponent} is in CHECK!")
            feature_log_event(game_id, "CHECK", f"{opponent} is in check!")

        if val_resp.checkmate:
            print(f"\n  ♛ CHECKMATE! {turn} wins!")
            feature_log_event(game_id, "CHECKMATE", f"{turn} wins by checkmate!")
            break

        # Switch turns
        turn = "BLACK" if turn == "WHITE" else "WHITE"
        move_num += 1

    # ── Game over: export log ──
    print("\n" + "=" * 58)
    print("  Game Over — Final Log")
    print("=" * 58)
    print(feature_export_log(game_id))


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not check_services():
        print("\n  Some microservices are not running.")
        print("  Start them all with:  python3 start_all.py\n")
        sys.exit(1)
    run_game()
