"""
integration_test.py  —  Chess Trainer
CS 361 Final Project

Runs a scripted sequence of calls against all four running microservices
and reports pass/fail for each. Demonstrates every communication pipe.

Run after start_all.py (or after starting each server manually):
    python3 integration_test.py
"""

import grpc
import json
import sys
import os
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "services", "validation"))
sys.path.insert(0, os.path.join(BASE, "services", "engine"))
sys.path.insert(0, os.path.join(BASE, "services", "timer"))
sys.path.insert(0, os.path.join(BASE, "services", "chat"))

import chess_pb2,  chess_pb2_grpc
import engine_pb2, engine_pb2_grpc
import timer_pb2,  timer_pb2_grpc
import chat_pb2,   chat_pb2_grpc

validator = chess_pb2_grpc.MoveValidatorStub(grpc.insecure_channel("localhost:50051"))
engine    = engine_pb2_grpc.ChessEngineStub(grpc.insecure_channel("localhost:50052"))
timer     = timer_pb2_grpc.TurnTimerStub(grpc.insecure_channel("localhost:50053"))
chat      = chat_pb2_grpc.ChatServiceStub(grpc.insecure_channel("localhost:50054"))

GAME_ID = "integration_test_001"

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

passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    status = "PASS" if condition else "FAIL"
    if condition:
        passed += 1
    else:
        failed += 1
    print(f"  [{status}] {name}")
    if detail:
        print(f"         {detail}")

def section(title):
    print(f"\n── {title} {'─' * (48 - len(title))}")

# ─────────────────────────────────────────────────────────────────────────────

print("=" * 58)
print("   Chess Trainer — Integration Test Suite")
print("=" * 58)

board = dict(STARTING_BOARD)
board_json = json.dumps(board)

# ── Microservice A: Move Validation ──────────────────────────────────────────
section("Microservice A  —  Move Validation  (port 50051)")

r = validator.ValidateMove(chess_pb2.ValidateMoveRequest(
    game_id="t", player_id="white", piece_position="E2",
    target_position="E4", move_type="NORMAL", board_state=board_json))
test("Valid pawn move E2→E4 accepted", r.is_valid, f"is_valid={r.is_valid}")

r = validator.ValidateMove(chess_pb2.ValidateMoveRequest(
    game_id="t", player_id="white", piece_position="E2",
    target_position="E5", move_type="NORMAL", board_state=board_json))
test("Illegal pawn move E2→E5 rejected", not r.is_valid, f"error='{r.error_message}'")

r = validator.ValidateMove(chess_pb2.ValidateMoveRequest(
    game_id="t", player_id="white", piece_position="G1",
    target_position="F3", move_type="NORMAL", board_state=board_json))
test("Knight G1→F3 accepted", r.is_valid)

r = validator.ValidateMove(chess_pb2.ValidateMoveRequest(
    game_id="t", player_id="white", piece_position="C1",
    target_position="E3", move_type="NORMAL", board_state=board_json))
test("Bishop blocked C1→E3 rejected", not r.is_valid, f"error='{r.error_message}'")

# ── Microservice B: Chess Engine ──────────────────────────────────────────────
section("Microservice B  —  Chess Engine  (port 50052)")

r = engine.GetBestMoves(engine_pb2.BestMovesRequest(
    game_id=GAME_ID, board_state=board_json, active_color="WHITE"))
test("Returns 3 suggested moves for WHITE", len(r.moves) == 3,
     f"got {len(r.moves)} moves")
test("Moves are ranked 1, 2, 3",
     [m.rank for m in r.moves] == [1, 2, 3],
     f"ranks={[m.rank for m in r.moves]}")
test("Each move has a reasoning string",
     all(m.reasoning for m in r.moves))
for m in r.moves:
    print(f"         #{m.rank} {m.piece_position}→{m.target_position}"
          f"  score={m.score}  | {m.reasoning}")

r = engine.GetBestMoves(engine_pb2.BestMovesRequest(
    game_id=GAME_ID, board_state=board_json, active_color="BLACK"))
test("Returns 3 suggested moves for BLACK", len(r.moves) == 3)

# ── Microservice C: Turn Timer ────────────────────────────────────────────────
section("Microservice C  —  Turn Timer  (port 50053)")

r = timer.ConfigTimer(timer_pb2.ConfigTimerRequest(
    game_id=GAME_ID, seconds_per_player=60))
test("Timer configured with 60s per player", r.success)

r = timer.StartTurn(timer_pb2.StartTurnRequest(
    game_id=GAME_ID, active_color="WHITE"))
test("White's turn started", r.success,
     f"seconds_remaining={r.seconds_remaining}")
test("White starts with 60s", r.seconds_remaining == 60)

time.sleep(2)

r = timer.CheckTime(timer_pb2.CheckTimeRequest(
    game_id=GAME_ID, active_color="WHITE"))
test("CheckTime returns remaining seconds", r.seconds_remaining > 0,
     f"remaining={r.seconds_remaining}s")
test("Time not expired after 2s", not r.time_expired)
test("2 seconds have elapsed from 60s bank", r.seconds_remaining <= 58,
     f"remaining={r.seconds_remaining}")

r = timer.EndTurn(timer_pb2.EndTurnRequest(
    game_id=GAME_ID, active_color="WHITE"))
test("EndTurn deducts elapsed time", r.success,
     f"used={r.seconds_used}s remaining={r.seconds_remaining}s")
test("Seconds used >= 2", r.seconds_used >= 2)

# ── Microservice D: Chat / Game Log ───────────────────────────────────────────
section("Microservice D  —  Chat / Game Log  (port 50054)")

r = chat.LogGameEvent(chat_pb2.LogEventRequest(
    game_id=GAME_ID, event_type="GAME_START",
    description="Integration test game started"))
test("Game start event logged", r.success, f"timestamp={r.timestamp}")

r = chat.LogGameEvent(chat_pb2.LogEventRequest(
    game_id=GAME_ID, event_type="MOVE",
    description="White played E2→E4"))
test("Move event logged", r.success)

r = chat.PostMessage(chat_pb2.PostMessageRequest(
    game_id=GAME_ID, player_id="WHITE",
    message="Nice opening!"))
test("Chat message posted", r.success, f"timestamp={r.timestamp}")

r = chat.PostMessage(chat_pb2.PostMessageRequest(
    game_id=GAME_ID, player_id="BLACK",
    message="Thanks, good game so far"))
test("Second chat message posted", r.success)

r = chat.GetMessages(chat_pb2.GetMessagesRequest(game_id=GAME_ID, limit=0))
test("GetMessages returns all 4 entries", len(r.entries) == 4,
     f"got {len(r.entries)} entries")
test("Entry types correct (EVENT, EVENT, CHAT, CHAT)",
     [e.entry_type for e in r.entries] == ["EVENT","EVENT","CHAT","CHAT"])

r = chat.ExportLog(chat_pb2.ExportLogRequest(game_id=GAME_ID))
test("ExportLog returns non-empty log", len(r.full_log) > 0)
test("Export total_entries == 4", r.total_entries == 4)
print(f"\n  Exported log preview:\n")
for line in r.full_log.split("\n"):
    print(f"    {line}")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 58)
print(f"  Results: {passed} passed / {failed} failed / {passed+failed} total")
print("=" * 58)
