from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import Dict, List, Optional, Tuple
import json
import uuid
import os
from datetime import datetime
import copy

# MongoDB setup
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_game_db")

app = FastAPI(title="Chess Multiplayer API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# Pydantic models
class GameMove(BaseModel):
    from_square: str
    to_square: str
    piece: str
    player: str
    timestamp: datetime = None
    is_castling: bool = False
    is_en_passant: bool = False
    promoted_to: Optional[str] = None

class GameRoom(BaseModel):
    room_id: str
    player1_id: Optional[str] = None
    player2_id: Optional[str] = None
    player1_name: Optional[str] = None
    player2_name: Optional[str] = None
    current_turn: str = "white"
    moves: List[GameMove] = []
    game_status: str = "waiting"  # waiting, active, finished, resigned
    winner: Optional[str] = None
    resignation_by: Optional[str] = None
    undo_requests: List[str] = []  # List of player IDs who requested undo
    rematch_requests: List[str] = []  # List of player IDs who requested rematch
    last_move_time: Optional[datetime] = None
    white_king_moved: bool = False
    black_king_moved: bool = False
    white_rook_a1_moved: bool = False
    white_rook_h1_moved: bool = False
    black_rook_a8_moved: bool = False
    black_rook_h8_moved: bool = False
    en_passant_target: Optional[str] = None
    created_at: datetime = None

class Player(BaseModel):
    player_id: str
    name: str
    color: Optional[str] = None

# In-memory storage for active connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.room_connections: Dict[str, List[str]] = {}

    async def connect(self, websocket: WebSocket, player_id: str):
        await websocket.accept()
        self.active_connections[player_id] = websocket

    def disconnect(self, player_id: str):
        if player_id in self.active_connections:
            del self.active_connections[player_id]
        
        # Remove from all rooms
        for room_id in list(self.room_connections.keys()):
            if player_id in self.room_connections[room_id]:
                self.room_connections[room_id].remove(player_id)
                if not self.room_connections[room_id]:
                    del self.room_connections[room_id]

    async def send_personal_message(self, message: str, player_id: str):
        if player_id in self.active_connections:
            try:
                await self.active_connections[player_id].send_text(message)
            except:
                # Connection might be closed
                pass

    async def broadcast_to_room(self, message: str, room_id: str, exclude_player: str = None):
        if room_id in self.room_connections:
            for player_id in self.room_connections[room_id]:
                if player_id != exclude_player and player_id in self.active_connections:
                    try:
                        await self.active_connections[player_id].send_text(message)
                    except:
                        # Connection might be closed
                        pass

    def add_to_room(self, player_id: str, room_id: str):
        if room_id not in self.room_connections:
            self.room_connections[room_id] = []
        if player_id not in self.room_connections[room_id]:
            self.room_connections[room_id].append(player_id)

manager = ConnectionManager()

# Chess game logic
def get_initial_board():
    """Returns the initial chess board setup"""
    return {
        "a8": "black_rook", "b8": "black_knight", "c8": "black_bishop", "d8": "black_queen",
        "e8": "black_king", "f8": "black_bishop", "g8": "black_knight", "h8": "black_rook",
        "a7": "black_pawn", "b7": "black_pawn", "c7": "black_pawn", "d7": "black_pawn",
        "e7": "black_pawn", "f7": "black_pawn", "g7": "black_pawn", "h7": "black_pawn",
        "a2": "white_pawn", "b2": "white_pawn", "c2": "white_pawn", "d2": "white_pawn",
        "e2": "white_pawn", "f2": "white_pawn", "g2": "white_pawn", "h2": "white_pawn",
        "a1": "white_rook", "b1": "white_knight", "c1": "white_bishop", "d1": "white_queen",
        "e1": "white_king", "f1": "white_bishop", "g1": "white_knight", "h1": "white_rook"
    }

def square_to_coords(square: str) -> Tuple[int, int]:
    """Convert square notation to coordinates (0-7, 0-7)"""
    file = ord(square[0]) - ord('a')
    rank = int(square[1]) - 1
    return (file, rank)

def coords_to_square(file: int, rank: int) -> str:
    """Convert coordinates to square notation"""
    return chr(ord('a') + file) + str(rank + 1)

def is_valid_chess_move(board: Dict[str, str], from_square: str, to_square: str, 
                       piece: str, current_turn: str, room_data: dict) -> Tuple[bool, str]:
    """Comprehensive chess move validation"""
    if not piece.startswith(current_turn):
        return False, "Not your piece"
    
    if from_square == to_square:
        return False, "Cannot move to same square"
    
    if to_square in board and board[to_square].startswith(current_turn):
        return False, "Cannot capture your own piece"
    
    from_file, from_rank = square_to_coords(from_square)
    to_file, to_rank = square_to_coords(to_square)
    
    piece_type = piece.split('_')[1]
    color = piece.split('_')[0]
    
    # Basic piece movement validation
    if piece_type == 'pawn':
        return validate_pawn_move(board, from_file, from_rank, to_file, to_rank, color, room_data)
    elif piece_type == 'rook':
        return validate_rook_move(board, from_file, from_rank, to_file, to_rank)
    elif piece_type == 'knight':
        return validate_knight_move(from_file, from_rank, to_file, to_rank)
    elif piece_type == 'bishop':
        return validate_bishop_move(board, from_file, from_rank, to_file, to_rank)
    elif piece_type == 'queen':
        return validate_queen_move(board, from_file, from_rank, to_file, to_rank)
    elif piece_type == 'king':
        return validate_king_move(board, from_file, from_rank, to_file, to_rank, color, room_data)
    
    return False, "Invalid piece"

def validate_pawn_move(board: Dict[str, str], from_file: int, from_rank: int, 
                      to_file: int, to_rank: int, color: str, room_data: dict) -> Tuple[bool, str]:
    """Validate pawn movement"""
    direction = 1 if color == 'white' else -1
    start_rank = 1 if color == 'white' else 6
    
    # Forward move
    if from_file == to_file:
        if to_rank == from_rank + direction:
            # One square forward
            to_square = coords_to_square(to_file, to_rank)
            if to_square in board:
                return False, "Path blocked"
            return True, ""
        elif to_rank == from_rank + (2 * direction) and from_rank == start_rank:
            # Two squares forward from start
            to_square = coords_to_square(to_file, to_rank)
            if to_square in board:
                return False, "Path blocked"
            return True, ""
    
    # Diagonal capture
    elif abs(from_file - to_file) == 1 and to_rank == from_rank + direction:
        to_square = coords_to_square(to_file, to_rank)
        if to_square in board:
            return True, ""
        # En passant
        elif room_data.get('en_passant_target') == to_square:
            return True, "en_passant"
    
    return False, "Invalid pawn move"

def validate_rook_move(board: Dict[str, str], from_file: int, from_rank: int, 
                      to_file: int, to_rank: int) -> Tuple[bool, str]:
    """Validate rook movement"""
    if from_file != to_file and from_rank != to_rank:
        return False, "Rook moves horizontally or vertically"
    
    # Check if path is clear
    file_step = 0 if from_file == to_file else (1 if to_file > from_file else -1)
    rank_step = 0 if from_rank == to_rank else (1 if to_rank > from_rank else -1)
    
    current_file, current_rank = from_file + file_step, from_rank + rank_step
    while current_file != to_file or current_rank != to_rank:
        square = coords_to_square(current_file, current_rank)
        if square in board:
            return False, "Path blocked"
        current_file += file_step
        current_rank += rank_step
    
    return True, ""

def validate_knight_move(from_file: int, from_rank: int, to_file: int, to_rank: int) -> Tuple[bool, str]:
    """Validate knight movement"""
    file_diff = abs(from_file - to_file)
    rank_diff = abs(from_rank - to_rank)
    
    if (file_diff == 2 and rank_diff == 1) or (file_diff == 1 and rank_diff == 2):
        return True, ""
    
    return False, "Invalid knight move"

def validate_bishop_move(board: Dict[str, str], from_file: int, from_rank: int, 
                        to_file: int, to_rank: int) -> Tuple[bool, str]:
    """Validate bishop movement"""
    if abs(from_file - to_file) != abs(from_rank - to_rank):
        return False, "Bishop moves diagonally"
    
    # Check if path is clear
    file_step = 1 if to_file > from_file else -1
    rank_step = 1 if to_rank > from_rank else -1
    
    current_file, current_rank = from_file + file_step, from_rank + rank_step
    while current_file != to_file:
        square = coords_to_square(current_file, current_rank)
        if square in board:
            return False, "Path blocked"
        current_file += file_step
        current_rank += rank_step
    
    return True, ""

def validate_queen_move(board: Dict[str, str], from_file: int, from_rank: int, 
                       to_file: int, to_rank: int) -> Tuple[bool, str]:
    """Validate queen movement (combination of rook and bishop)"""
    rook_valid, rook_msg = validate_rook_move(board, from_file, from_rank, to_file, to_rank)
    if rook_valid:
        return True, ""
    
    bishop_valid, bishop_msg = validate_bishop_move(board, from_file, from_rank, to_file, to_rank)
    if bishop_valid:
        return True, ""
    
    return False, "Invalid queen move"

def validate_king_move(board: Dict[str, str], from_file: int, from_rank: int, 
                      to_file: int, to_rank: int, color: str, room_data: dict) -> Tuple[bool, str]:
    """Validate king movement including castling"""
    file_diff = abs(from_file - to_file)
    rank_diff = abs(from_rank - to_rank)
    
    # Normal king move (one square in any direction)
    if file_diff <= 1 and rank_diff <= 1:
        return True, ""
    
    # Castling
    if rank_diff == 0 and file_diff == 2:
        if color == 'white' and from_rank == 0 and not room_data.get('white_king_moved'):
            # White castling
            if to_file == 6 and not room_data.get('white_rook_h1_moved'):  # Kingside
                if 'f1' not in board and 'g1' not in board:
                    return True, "castling_kingside"
            elif to_file == 2 and not room_data.get('white_rook_a1_moved'):  # Queenside
                if 'b1' not in board and 'c1' not in board and 'd1' not in board:
                    return True, "castling_queenside"
        elif color == 'black' and from_rank == 7 and not room_data.get('black_king_moved'):
            # Black castling
            if to_file == 6 and not room_data.get('black_rook_h8_moved'):  # Kingside
                if 'f8' not in board and 'g8' not in board:
                    return True, "castling_kingside"
            elif to_file == 2 and not room_data.get('black_rook_a8_moved'):  # Queenside
                if 'b8' not in board and 'c8' not in board and 'd8' not in board:
                    return True, "castling_queenside"
    
    return False, "Invalid king move"

def is_in_check(board: Dict[str, str], color: str) -> bool:
    """Check if the king of given color is in check"""
    # Find king position
    king_square = None
    for square, piece in board.items():
        if piece == f"{color}_king":
            king_square = square
            break
    
    if not king_square:
        return False
    
    # Check if any opponent piece can attack the king
    opponent_color = "black" if color == "white" else "white"
    for square, piece in board.items():
        if piece.startswith(opponent_color):
            # Simplified check - would need full move validation in real implementation
            pass
    
    return False  # Placeholder

# API Routes
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "message": "Chess game server running"}

@app.post("/api/rooms")
async def create_room():
    """Create a new game room"""
    room_id = str(uuid.uuid4())[:8]
    game_room = GameRoom(
        room_id=room_id,
        created_at=datetime.utcnow()
    )
    
    await db.game_rooms.insert_one(game_room.dict())
    return {"room_id": room_id, "status": "created"}

@app.get("/api/rooms/{room_id}")
async def get_room(room_id: str):
    """Get room details"""
    room = await db.game_rooms.find_one({"room_id": room_id})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Remove MongoDB _id for JSON serialization
    room.pop("_id", None)
    return room

@app.post("/api/rooms/{room_id}/join")
async def join_room(room_id: str, player: Player):
    """Join a game room"""
    room = await db.game_rooms.find_one({"room_id": room_id})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Assign player color and position
    if not room.get("player1_id"):
        await db.game_rooms.update_one(
            {"room_id": room_id},
            {"$set": {
                "player1_id": player.player_id, 
                "player1_name": player.name,
                "game_status": "waiting"
            }}
        )
        player_color = "white"
    elif not room.get("player2_id"):
        await db.game_rooms.update_one(
            {"room_id": room_id},
            {"$set": {
                "player2_id": player.player_id, 
                "player2_name": player.name,
                "game_status": "active"
            }}
        )
        player_color = "black"
    else:
        raise HTTPException(status_code=400, detail="Room is full")
    
    return {"player_id": player.player_id, "color": player_color, "room_id": room_id}

@app.get("/api/rooms/{room_id}/board")
async def get_board_state(room_id: str):
    """Get current board state"""
    room = await db.game_rooms.find_one({"room_id": room_id})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Calculate current board state from moves
    board = get_initial_board()
    for move in room.get("moves", []):
        if move["from_square"] in board:
            piece = board.pop(move["from_square"])
            board[move["to_square"]] = piece
    
    return {
        "board": board,
        "current_turn": room.get("current_turn", "white"),
        "game_status": room.get("game_status", "waiting"),
        "player1_name": room.get("player1_name"),
        "player2_name": room.get("player2_name"),
        "winner": room.get("winner"),
        "undo_requests": room.get("undo_requests", []),
        "rematch_requests": room.get("rematch_requests", [])
    }

@app.post("/api/rooms/{room_id}/resign/{player_id}")
async def resign_game(room_id: str, player_id: str):
    """Resign from the game"""
    room = await db.game_rooms.find_one({"room_id": room_id})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if room.get("player1_id") == player_id:
        winner = room.get("player2_id")
    elif room.get("player2_id") == player_id:
        winner = room.get("player1_id")
    else:
        raise HTTPException(status_code=400, detail="Player not in this game")
    
    await db.game_rooms.update_one(
        {"room_id": room_id},
        {"$set": {
            "game_status": "resigned",
            "winner": winner,
            "resignation_by": player_id
        }}
    )
    
    return {"status": "resigned", "winner": winner}

@app.post("/api/rooms/{room_id}/undo/{player_id}")
async def request_undo(room_id: str, player_id: str):
    """Request to undo the last move"""
    room = await db.game_rooms.find_one({"room_id": room_id})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    undo_requests = room.get("undo_requests", [])
    if player_id not in undo_requests:
        undo_requests.append(player_id)
        
        await db.game_rooms.update_one(
            {"room_id": room_id},
            {"$set": {"undo_requests": undo_requests}}
        )
    
    return {"status": "undo_requested", "requests": undo_requests}

@app.post("/api/rooms/{room_id}/rematch/{player_id}")
async def request_rematch(room_id: str, player_id: str):
    """Request a rematch"""
    room = await db.game_rooms.find_one({"room_id": room_id})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    rematch_requests = room.get("rematch_requests", [])
    if player_id not in rematch_requests:
        rematch_requests.append(player_id)
        
        # If both players requested rematch, start new game
        if len(rematch_requests) == 2:
            await db.game_rooms.update_one(
                {"room_id": room_id},
                {"$set": {
                    "moves": [],
                    "current_turn": "white",
                    "game_status": "active",
                    "winner": None,
                    "resignation_by": None,
                    "undo_requests": [],
                    "rematch_requests": [],
                    "white_king_moved": False,
                    "black_king_moved": False,
                    "white_rook_a1_moved": False,
                    "white_rook_h1_moved": False,
                    "black_rook_a8_moved": False,
                    "black_rook_h8_moved": False,
                    "en_passant_target": None
                }}
            )
            return {"status": "rematch_started"}
        else:
            await db.game_rooms.update_one(
                {"room_id": room_id},
                {"$set": {"rematch_requests": rematch_requests}}
            )
    
    return {"status": "rematch_requested", "requests": rematch_requests}

# WebSocket endpoint
@app.websocket("/api/ws/{room_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_id: str):
    await manager.connect(websocket, player_id)
    manager.add_to_room(player_id, room_id)
    
    try:
        # Send initial board state
        room = await db.game_rooms.find_one({"room_id": room_id})
        if room:
            board = get_initial_board()
            for move in room.get("moves", []):
                if move["from_square"] in board:
                    piece = board.pop(move["from_square"])
                    board[move["to_square"]] = piece
            
            await manager.send_personal_message(
                json.dumps({
                    "type": "board_state",
                    "board": board,
                    "current_turn": room.get("current_turn", "white"),
                    "game_status": room.get("game_status", "waiting"),
                    "player1_name": room.get("player1_name"),
                    "player2_name": room.get("player2_name"),
                    "undo_requests": room.get("undo_requests", []),
                    "rematch_requests": room.get("rematch_requests", [])
                }),
                player_id
            )
        
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "move":
                # Validate and process move
                room = await db.game_rooms.find_one({"room_id": room_id})
                if room and room.get("current_turn") == message.get("player_color"):
                    # Get current board state
                    board = get_initial_board()
                    for move in room.get("moves", []):
                        if move["from_square"] in board:
                            piece = board.pop(move["from_square"])
                            board[move["to_square"]] = piece
                    
                    # Validate move
                    piece = board.get(message["from_square"])
                    if piece:
                        is_valid, move_type = is_valid_chess_move(
                            board, 
                            message["from_square"], 
                            message["to_square"], 
                            piece, 
                            message.get("player_color"),
                            room
                        )
                        
                        if is_valid:
                            move = GameMove(
                                from_square=message["from_square"],
                                to_square=message["to_square"],
                                piece=piece,
                                player=player_id,
                                timestamp=datetime.utcnow(),
                                is_castling="castling" in move_type,
                                is_en_passant=move_type == "en_passant"
                            )
                            
                            # Update database
                            next_turn = "black" if room.get("current_turn") == "white" else "white"
                            update_data = {
                                "$push": {"moves": move.dict()},
                                "$set": {
                                    "current_turn": next_turn,
                                    "last_move_time": datetime.utcnow(),
                                    "undo_requests": []  # Clear undo requests after move
                                }
                            }
                            
                            # Update castling flags
                            if piece == "white_king":
                                update_data["$set"]["white_king_moved"] = True
                            elif piece == "black_king":
                                update_data["$set"]["black_king_moved"] = True
                            elif piece == "white_rook" and message["from_square"] == "a1":
                                update_data["$set"]["white_rook_a1_moved"] = True
                            elif piece == "white_rook" and message["from_square"] == "h1":
                                update_data["$set"]["white_rook_h1_moved"] = True
                            elif piece == "black_rook" and message["from_square"] == "a8":
                                update_data["$set"]["black_rook_a8_moved"] = True
                            elif piece == "black_rook" and message["from_square"] == "h8":
                                update_data["$set"]["black_rook_h8_moved"] = True
                            
                            await db.game_rooms.update_one(
                                {"room_id": room_id},
                                update_data
                            )
                            
                            # Broadcast move to all players in room
                            await manager.broadcast_to_room(
                                json.dumps({
                                    "type": "move",
                                    "from_square": message["from_square"],
                                    "to_square": message["to_square"],
                                    "piece": piece,
                                    "player": player_id,
                                    "current_turn": next_turn,
                                    "move_type": move_type
                                }),
                                room_id
                            )
                        else:
                            # Send invalid move message
                            await manager.send_personal_message(
                                json.dumps({
                                    "type": "invalid_move",
                                    "reason": move_type
                                }),
                                player_id
                            )
            
            elif message["type"] == "webrtc_signal":
                # Forward WebRTC signaling messages
                await manager.broadcast_to_room(
                    json.dumps({
                        "type": "webrtc_signal",
                        "signal": message["signal"],
                        "from_player": player_id
                    }),
                    room_id,
                    exclude_player=player_id
                )
            
            elif message["type"] == "game_action":
                # Handle game actions (resign, undo, rematch)
                action = message.get("action")
                if action == "resign":
                    await resign_game(room_id, player_id)
                    await manager.broadcast_to_room(
                        json.dumps({
                            "type": "game_resigned",
                            "resigned_by": player_id
                        }),
                        room_id
                    )
                elif action == "undo_request":
                    await request_undo(room_id, player_id)
                    await manager.broadcast_to_room(
                        json.dumps({
                            "type": "undo_requested",
                            "requested_by": player_id
                        }),
                        room_id
                    )
                elif action == "rematch_request":
                    result = await request_rematch(room_id, player_id)
                    await manager.broadcast_to_room(
                        json.dumps({
                            "type": "rematch_requested" if result["status"] == "rematch_requested" else "rematch_started",
                            "requested_by": player_id
                        }),
                        room_id
                    )
                
    except WebSocketDisconnect:
        manager.disconnect(player_id)
        await manager.broadcast_to_room(
            json.dumps({
                "type": "player_disconnected",
                "player_id": player_id
            }),
            room_id
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)