# Multiplayer Online Chess Game

A real-time multiplayer chess game built with React frontend and FastAPI backend, featuring WebSocket communication, voice chat, and comprehensive chess rules validation.

## Features

- ✅ Real-time multiplayer gameplay with WebSocket + REST API fallback
- ✅ 3D chess pieces with drag & drop interface
- ✅ Voice chat using WebRTC
- ✅ Complete chess rules validation (castling, en passant, etc.)
- ✅ Game actions: resign, undo requests, rematch
- ✅ Room sharing and spectator mode
- ✅ Responsive design for mobile and desktop
- ✅ In-memory storage fallback (no MongoDB required)

## Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- npm or yarn

### Installation & Running

1. **Clone and install dependencies:**
```bash
# Install backend dependencies
cd backend
pip install -r requirements.txt

# Install frontend dependencies  
cd ../frontend
npm install
```

2. **Start the application:**

**Option 1: Start both services together (recommended)**
```bash
# From root directory
npm install concurrently
npm start
```

**Option 2: Start services separately**
```bash
# Terminal 1 - Backend
cd backend
python server.py

# Terminal 2 - Frontend  
cd frontend
npm start
```

3. **Access the game:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8001
- API Documentation: http://localhost:8001/docs

## How to Play

1. **Create a Room:** Click "Create Room" to start a new game
2. **Share Room ID:** Copy and share the room ID with your opponent
3. **Join Game:** Your opponent enters the room ID and clicks "Join Room"
4. **Play Chess:** 
   - White player moves first
   - Click a piece to select it, then click destination square
   - Drag and drop pieces for smoother gameplay
5. **Game Features:**
   - Voice chat: Click "Start Voice Chat" to communicate
   - Resign: End the game early
   - Request Undo: Ask opponent to undo last move
   - Rematch: Start a new game in the same room

## Architecture

### Backend (FastAPI + Python)
- **REST API:** Room management, game state, player actions
- **WebSocket:** Real-time move synchronization and game events
- **Storage:** In-memory fallback with optional MongoDB support
- **Chess Engine:** Complete rules validation including special moves

### Frontend (React)
- **Real-time UI:** WebSocket integration with REST API fallback
- **3D Chess Board:** CSS transforms and animations
- **WebRTC:** Peer-to-peer voice communication
- **Responsive Design:** Works on desktop and mobile devices

## Configuration

### Environment Variables

**Backend (.env):**
```env
MONGO_URL=mongodb://localhost:27017  # Optional
DB_NAME=chess_game_db
PORT=8001
```

**Frontend (.env):**
```env
REACT_APP_BACKEND_URL=http://localhost:8001
```

## API Endpoints

- `POST /api/rooms` - Create new game room
- `GET /api/rooms/{room_id}` - Get room details
- `POST /api/rooms/{room_id}/join` - Join game room
- `GET /api/rooms/{room_id}/board` - Get current board state
- `POST /api/rooms/{room_id}/resign/{player_id}` - Resign game
- `POST /api/rooms/{room_id}/undo/{player_id}` - Request undo
- `POST /api/rooms/{room_id}/rematch/{player_id}` - Request rematch
- `WS /api/ws/{room_id}/{player_id}` - WebSocket connection

## Testing

```bash
# Test backend API
python backend_test.py

# Test frontend
cd frontend
npm test
```

## Deployment

The application is optimized for easy deployment:

- **Backend:** Can run with or without MongoDB
- **Frontend:** Static build for any web server
- **WebSocket:** Automatic fallback to REST API polling
- **CORS:** Configured for cross-origin requests

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failed:**
   - The app automatically falls back to REST API polling
   - Check firewall settings for WebSocket connections

2. **Voice Chat Not Working:**
   - Ensure microphone permissions are granted
   - HTTPS required for WebRTC in production

3. **MongoDB Connection Error:**
   - App works without MongoDB using in-memory storage
   - Install MongoDB if persistent storage is needed

4. **Port Already in Use:**
   - Change PORT in backend/.env
   - Update REACT_APP_BACKEND_URL in frontend/.env

### Debug Mode

Enable debug logging by checking browser console and backend logs for detailed information about:
- WebSocket connections
- Move validation
- Game state changes
- API requests

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.