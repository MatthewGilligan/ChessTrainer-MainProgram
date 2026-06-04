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

# ── Add service stub directories to path ──────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "services", "validation"))
sys.path.insert(0, os.path.join(BASE, "services", "engine"))
sys.path.insert(0, os.path.join(BASE, "services", "timer"))
sys.path.insert(0, os.path.join(BASE, "services", "chat"))

import chess_pb2,  chess_pb2_grpc
import engine_pb2, engine_pb2_grpc
import timer_pb2,  timer_pb2_grpc
import chat_pb2,   chat_pb2_grpc

# ── gRPC stubs — one channel per microservice, no direct imports ───────────────
validator = chess_pb2_grpc.MoveValidatorStub(grpc.insecure_channel("localhost:50051"))
engine    = engine_pb2_grpc.ChessEngineStub(grpc.insecure_channel("localhost:50052"))
timer     = timer_pb2_grpc.TurnTimerStub(grpc.insecure_channel("localhost:50053"))
chat      = chat_pb2_grpc.ChatServiceStub(grpc.insecure_channel("localhost:50054"))

FILES = "ABCDEFGH"

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

WHITE_SYMBOLS = {"PAWN":"♙","ROOK":"♖","KNIGHT":"♘","BISHOP":"♗","QUEEN":"♕","KING":"♔"}
BLACK_SYMBOLS = {"PAWN":"♟","ROOK":"♜","KNIGHT":"♞","BISHOP":"♝","QUEEN":"♛","KING":"♚"}

# ── Display ────────────────────────────────────────────────────────────────────

def print_board(board):
    print("\n    A  B  C  D  E  F  G  H")
    print("   ─────────────────────────")
    for rank in range(8, 0, -1):
        row = f" {rank} │"
        for f in FILES:
            piece = board.get(f"{f}{rank}", "")
            if not piece:
                row += " . "
            elif piece.startswith("WHITE"):
                row += f" {WHITE_SYMBOLS.get(piece.split('_',1)[1], '?')} "
            else:
                row += f" {BLACK_SYMBOLS.get(piece.split('_',1)[1], '?')} "
        print(row)
    print("   ─────────────────────────\n")

def print_separator(title=""):
    if title:
        pad = (56 - len(title)) // 2
        print("\n" + "─" * pad + f"  {title}  " + "─" * pad)
    else:
        print("─" * 58)

# ── Service health check ───────────────────────────────────────────────────────

def check_services():
    services = [
        ("Move Validation  (MS-A)", "localhost:50051"),
        ("Chess Engine     (MS-B)", "localhost:50052"),
        ("Turn Timer       (MS-C)", "localhost:50053"),
        ("Chat / Game Log  (MS-D)", "localhost:50054"),
    ]
    print("\nChecking microservices...")
    all_ok = True
    for name, addr in services:
        try:
            grpc.channel_ready_future(
                grpc.insecure_channel(addr)).result(timeout=2)
            print(f"  ✓  {name}  —  {addr}")
        except grpc.FutureTimeoutError:
            print(f"  ✗  {name}  —  {addr}  NOT RUNNING")
            all_ok = False
    return all_ok

# ── Microservice calls (each function = one microservice) ─────────────────────

def ms_validate(game_id, turn, src, dst, board):
    """MS-A: Is this move legal? Returns response with is_valid + updated_board."""
    print(f"\n  [MS-A] Validating {src}→{dst}...")
    r = validator.ValidateMove(chess_pb2.ValidateMoveRequest(
        game_id=game_id, player_id=turn.lower(),
        piece_position=src, target_position=dst,
        move_type="NORMAL", board_state=json.dumps(board),
    ))
    status = "✓ valid" if r.is_valid else f"✗ {r.error_message}"
    print(f"  [MS-A] Response: {status}" +
          ("  ♚ check!" if r.check_state else ""))
    return r

def ms_hints(game_id, board, color):
    """MS-B: Returns top 3 suggested moves for the active color."""
    print(f"  [MS-B] Requesting top 3 moves for {color}...")
    r = engine.GetBestMoves(engine_pb2.BestMovesRequest(
        game_id=game_id, board_state=json.dumps(board), active_color=color,
    ))
    if not r.error_message:
        for m in r.moves:
            print(f"  [MS-B]   #{m.rank} {m.piece_position}→{m.target_position}"
                  f"  (score {m.score})  {m.reasoning}")
    return r

def ms_config_timer(game_id, seconds):
    """MS-C: Set up time banks before the game starts."""
    print(f"  [MS-C] Configuring timer: {seconds}s per player")
    timer.ConfigTimer(timer_pb2.ConfigTimerRequest(
        game_id=game_id, seconds_per_player=seconds))

def ms_start_turn(game_id, color):
    """MS-C: Mark the start of a player's turn (begins countdown)."""
    r = timer.StartTurn(timer_pb2.StartTurnRequest(
        game_id=game_id, active_color=color))
    mins, secs = divmod(r.seconds_remaining, 60)
    print(f"  [MS-C] {color}'s turn started — {mins}m {secs:02d}s in bank")
    return r

def ms_check_time(game_id, color):
    """MS-C: Poll how much time the active player has left."""
    return timer.CheckTime(timer_pb2.CheckTimeRequest(
        game_id=game_id, active_color=color))

def ms_end_turn(game_id, color):
    """MS-C: End a player's turn and deduct time used from their bank."""
    r = timer.EndTurn(timer_pb2.EndTurnRequest(
        game_id=game_id, active_color=color))
    print(f"  [MS-C] {color} used {r.seconds_used}s"
          f"  —  {r.seconds_remaining}s remaining")
    return r

def ms_log_event(game_id, event_type, description):
    """MS-D: Record a game event (move, check, etc.) in the game log."""
    r = chat.LogGameEvent(chat_pb2.LogEventRequest(
        game_id=game_id, event_type=event_type, description=description))
    print(f"  [MS-D] Logged [{event_type}]: {description}")
    return r

def ms_post_chat(game_id, player_id, message):
    """MS-D: Store a player chat message."""
    r = chat.PostMessage(chat_pb2.PostMessageRequest(
        game_id=game_id, player_id=player_id, message=message))
    print(f"  [MS-D] Chat stored at {r.timestamp}")
    return r

def ms_get_chat(game_id, limit=8):
    """MS-D: Retrieve recent chat and event entries."""
    return chat.GetMessages(chat_pb2.GetMessagesRequest(
        game_id=game_id, limit=limit)).entries

def ms_export_log(game_id):
    """MS-D: Export the full annotated game log as a string."""
    return chat.ExportLog(chat_pb2.ExportLogRequest(game_id=game_id)).full_log

# ── Game loop ──────────────────────────────────────────────────────────────────

def run_game():
    game_id  = f"game_{int(time.time())}"
    board    = dict(STARTING_BOARD)
    turn     = "WHITE"
    move_num = 1
    hints_on = True

    print("\n" + "=" * 58)
    print("        Chess Trainer  —  CS 361 Final Project")
    print("=" * 58)
    print(f"  Game ID : {game_id}")
    print("  Microservices  A:50051  B:50052  C:50053  D:50054")
    print("=" * 58)

    # ── Timer config (MS-C) ──
    try:
        raw = input("\nSeconds per player? (default 300, Enter to skip): ").strip()
        seconds = int(raw) if raw.isdigit() and int(raw) > 0 else 300
    except (EOFError, KeyboardInterrupt):
        seconds = 300
    ms_config_timer(game_id, seconds)

    # ── Game start log (MS-D) ──
    ms_log_event(game_id, "GAME_START",
                 f"Game started — {seconds}s per player")

    print("\n  Commands:  E2 E4  |  hint  |  chat <msg>  |  log  |  quit\n")

    while True:
        print_board(board)
        print_separator(f"Move {move_num}  —  {turn}'s turn")

        # Start timer for this turn (MS-C)
        ms_start_turn(game_id, turn)

        # Hints (MS-B)
        if hints_on:
            hints_resp = ms_hints(game_id, board, turn)
            if hints_resp.moves:
                print("\n  Suggested moves:")
                for m in hints_resp.moves:
                    print(f"    #{m.rank}  {m.piece_position}→{m.target_position}"
                          f"  —  {m.reasoning}")
        else:
            print("  (hints off — type 'hint' to re-enable)")

        # Show time remaining (MS-C)
        time_resp = ms_check_time(game_id, turn)
        mins, secs = divmod(time_resp.seconds_remaining, 60)
        print(f"\n  ⏱  {turn}'s time: {mins}m {secs:02d}s remaining")

        if time_resp.time_expired:
            ms_end_turn(game_id, turn)
            print(f"\n  ⏰  {turn} ran out of time — game over!")
            ms_log_event(game_id, "FORFEIT", f"{turn} forfeited on time")
            break

        # Input
        try:
            raw = input(f"\n  {turn} > ").strip()
        except (EOFError, KeyboardInterrupt):
            raw = "quit"

        if not raw:
            continue

        # ── quit ──────────────────────────────────────────────────────────────
        if raw.lower() == "quit":
            ms_end_turn(game_id, turn)
            ms_log_event(game_id, "GAME_END", "Game ended by player")
            break

        # ── log ───────────────────────────────────────────────────────────────
        if raw.lower() == "log":
            print("\n" + ms_export_log(game_id))
            continue   # timer keeps running; no deduction for viewing the log

        # ── chat <msg> ────────────────────────────────────────────────────────
        if raw.lower().startswith("chat "):
            msg = raw[5:].strip()
            if msg:
                ms_post_chat(game_id, turn, msg)
                print("\n  Recent chat:")
                for e in ms_get_chat(game_id, limit=6):
                    icon = "♟" if e.entry_type == "EVENT" else "💬"
                    print(f"    [{e.timestamp}] {icon} {e.player_id}: {e.message}")
            continue   # timer keeps running; chat doesn't end your turn

        # ── hint toggle ───────────────────────────────────────────────────────
        if raw.lower() == "hint":
            hints_on = not hints_on
            print(f"  Hints {'ON ✓' if hints_on else 'OFF'}")
            continue

        # ── move ──────────────────────────────────────────────────────────────
        parts = raw.upper().split()
        if len(parts) != 2 or any(len(p) != 2 for p in parts):
            print("  Usage:  FROM TO   e.g.  E2 E4")
            continue

        src, dst = parts

        # Validate with MS-A BEFORE touching the timer
        val = ms_validate(game_id, turn, src, dst, board)

        if not val.is_valid:
            # Bad move — don't end the turn, don't deduct time
            print(f"\n  ✗  Illegal move: {val.error_message}")
            print("     Try again — your clock is still running.")
            continue

        # Move is valid — now end the timer and deduct (MS-C)
        ms_end_turn(game_id, turn)

        # Update board
        board = json.loads(val.updated_board)

        # Log the move (MS-D)
        ms_log_event(game_id, "MOVE", f"{turn} played {src}→{dst}")

        # Check / checkmate notifications
        if val.checkmate:
            print_board(board)
            print(f"\n  ♛  CHECKMATE!  {turn} wins!")
            ms_log_event(game_id, "CHECKMATE", f"{turn} wins by checkmate!")
            break

        if val.check_state:
            opponent = "BLACK" if turn == "WHITE" else "WHITE"
            print(f"\n  ♚  {opponent} is in CHECK!")
            ms_log_event(game_id, "CHECK", f"{opponent} is in check!")

        # Switch sides
        turn = "BLACK" if turn == "WHITE" else "WHITE"
        move_num += 1

    # ── Final log ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 58)
    print("  Game Over  —  Final Annotated Log")
    print("=" * 58)
    print(ms_export_log(game_id))


if __name__ == "__main__":
    if not check_services():
        print("\n  Start all microservices first:  python3 start_all.py\n")
        sys.exit(1)
    run_game()
