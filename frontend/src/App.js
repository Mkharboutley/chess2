import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

// Chess piece Unicode symbols with better visual distinction
const PIECE_SYMBOLS = {
  white_king: '♔',
  white_queen: '♕', 
  white_rook: '♖',
  white_bishop: '♗',
  white_knight: '♘',
  white_pawn: '♙',
  black_king: '♚',
  black_queen: '♛',
  black_rook: '♜', 
  black_bishop: '♝',
  black_knight: '♞',
  black_pawn: '♟'
};

function App() {
  const [gameState, setGameState] = useState('menu'); // menu, joining, playing
  const [roomId, setRoomId] = useState('');
  const [playerInfo, setPlayerInfo] = useState(null);
  const [board, setBoard] = useState({});
  const [currentTurn, setCurrentTurn] = useState('white');
  const [selectedSquare, setSelectedSquare] = useState(null);
  const [draggedPiece, setDraggedPiece] = useState(null);
  const [gameStatus, setGameStatus] = useState('waiting');
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [voiceConnected, setVoiceConnected] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [player1Name, setPlayer1Name] = useState('');
  const [player2Name, setPlayer2Name] = useState('');
  const [winner, setWinner] = useState(null);
  const [undoRequests, setUndoRequests] = useState([]);
  const [rematchRequests, setRematchRequests] = useState([]);
  const [moveHistory, setMoveHistory] = useState([]);
  const [invalidMoveMessage, setInvalidMoveMessage] = useState('');
  const [showRoomShare, setShowRoomShare] = useState(false);
  
  const wsRef = useRef(null);
  const peerConnectionRef = useRef(null);
  const localStreamRef = useRef(null);
  const remoteAudioRef = useRef(null);

  // Initialize board layout
  const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
  const ranks = ['8', '7', '6', '5', '4', '3', '2', '1'];

  // WebSocket connection
  const connectWebSocket = useCallback((roomId, playerId) => {
    const wsUrl = `${BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://')}/api/ws/${roomId}/${playerId}`;
    console.log('Connecting to WebSocket:', wsUrl);
    
    try {
      wsRef.current = new WebSocket(wsUrl);
      
      wsRef.current.onopen = () => {
        setConnectionStatus('connected');
        console.log('WebSocket connected successfully');
      };
      
      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('Received WebSocket message:', message);
          
          switch (message.type) {
            case 'board_state':
              console.log('Updating board from WebSocket:', message.board);
              setBoard(message.board || {});
              setCurrentTurn(message.current_turn || 'white');
              setGameStatus(message.game_status || 'waiting');
              setPlayer1Name(message.player1_name || '');
              setPlayer2Name(message.player2_name || '');
              setUndoRequests(message.undo_requests || []);
              setRematchRequests(message.rematch_requests || []);
              break;
            case 'move':
              setBoard(prevBoard => {
                const newBoard = { ...prevBoard };
                delete newBoard[message.from_square];
                newBoard[message.to_square] = message.piece;
                return newBoard;
              });
              setCurrentTurn(message.current_turn);
              setMoveHistory(prev => [...prev, {
                from: message.from_square,
                to: message.to_square,
                piece: message.piece,
                player: message.player
              }]);
              break;
            case 'invalid_move':
              setInvalidMoveMessage(message.reason);
              setTimeout(() => setInvalidMoveMessage(''), 3000);
              break;
            case 'webrtc_signal':
              handleWebRTCSignal(message.signal);
              break;
            case 'player_disconnected':
              console.log('Player disconnected:', message.player_id);
              break;
            case 'game_resigned':
              setGameStatus('resigned');
              setWinner(message.resigned_by === playerId ? 
                (playerInfo?.color === 'white' ? 'black' : 'white') : playerInfo?.color);
              break;
            case 'undo_requested':
              fetchBoardState();
              break;
            case 'rematch_requested':
              fetchBoardState();
              break;
            case 'rematch_started':
              setBoard({});
              setCurrentTurn('white');
              setGameStatus('active');
              setWinner(null);
              setMoveHistory([]);
              setUndoRequests([]);
              setRematchRequests([]);
              break;
            default:
              break;
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
      
      wsRef.current.onclose = (event) => {
        setConnectionStatus('disconnected');
        console.log('WebSocket disconnected:', event.code, event.reason);
        
        // Try to reconnect after a delay
        setTimeout(() => {
          if (gameState === 'playing') {
            console.log('Attempting WebSocket reconnection...');
            connectWebSocket(roomId, playerId);
          }
        }, 5000);
      };
      
      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionStatus('error');
        
        // Fallback to REST API polling
        console.log('WebSocket failed, using REST API fallback');
        const pollInterval = setInterval(async () => {
          if (gameState === 'playing' && connectionStatus !== 'connected') {
            try {
              await fetchBoardState();
            } catch (error) {
              console.error('Error in polling fallback:', error);
            }
          } else {
            clearInterval(pollInterval);
          }
        }, 3000);
      };
      
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      setConnectionStatus('error');
      
      // Use REST API as fallback
      const pollInterval = setInterval(async () => {
        if (gameState === 'playing') {
          try {
            await fetchBoardState();
          } catch (error) {
            console.error('Error in REST API fallback:', error);
          }
        } else {
          clearInterval(pollInterval);
        }
      }, 3000);
    }
  }, [gameState, connectionStatus, playerInfo]);

  // Fetch board state from REST API as fallback
  const fetchBoardState = async (roomId = null) => {
    const targetRoomId = roomId || playerInfo?.room_id;
    if (!targetRoomId) return;
    
    console.log('Fetching board state for room:', targetRoomId);
    try {
      const response = await fetch(`${BACKEND_URL}/api/rooms/${targetRoomId}/board`);
      if (response.ok) {
        const data = await response.json();
        console.log('Board state received:', data);
        setBoard(data.board || {});
        setCurrentTurn(data.current_turn || 'white');
        setGameStatus(data.game_status || 'waiting');
        setPlayer1Name(data.player1_name || '');
        setPlayer2Name(data.player2_name || '');
        setWinner(data.winner);
        setUndoRequests(data.undo_requests || []);
        setRematchRequests(data.rematch_requests || []);
      } else {
        console.error('Failed to fetch board state:', response.status);
      }
    } catch (error) {
      console.error('Error fetching board state:', error);
    }
  };

  // WebRTC setup for voice chat
  const initializeWebRTC = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      localStreamRef.current = stream;
      
      const configuration = {
        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
      };
      
      peerConnectionRef.current = new RTCPeerConnection(configuration);
      
      stream.getTracks().forEach(track => {
        peerConnectionRef.current.addTrack(track, stream);
      });
      
      peerConnectionRef.current.ontrack = (event) => {
        if (remoteAudioRef.current) {
          remoteAudioRef.current.srcObject = event.streams[0];
          setVoiceConnected(true);
        }
      };
      
      peerConnectionRef.current.onicecandidate = (event) => {
        if (event.candidate && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({
            type: 'webrtc_signal',
            signal: {
              type: 'ice-candidate',
              candidate: event.candidate
            }
          }));
        }
      };
      
    } catch (error) {
      console.error('Error accessing microphone:', error);
    }
  };

  const handleWebRTCSignal = async (signal) => {
    if (!peerConnectionRef.current) return;
    
    try {
      switch (signal.type) {
        case 'offer':
          await peerConnectionRef.current.setRemoteDescription(signal.offer);
          const answer = await peerConnectionRef.current.createAnswer();
          await peerConnectionRef.current.setLocalDescription(answer);
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
              type: 'webrtc_signal',
              signal: {
                type: 'answer',
                answer: answer
              }
            }));
          }
          break;
        case 'answer':
          await peerConnectionRef.current.setRemoteDescription(signal.answer);
          break;
        case 'ice-candidate':
          await peerConnectionRef.current.addIceCandidate(signal.candidate);
          break;
        default:
          break;
      }
    } catch (error) {
      console.error('WebRTC signaling error:', error);
    }
  };

  const startVoiceCall = async () => {
    if (!peerConnectionRef.current) return;
    
    try {
      const offer = await peerConnectionRef.current.createOffer();
      await peerConnectionRef.current.setLocalDescription(offer);
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'webrtc_signal',
          signal: {
            type: 'offer',
            offer: offer
          }
        }));
      }
    } catch (error) {
      console.error('Error starting voice call:', error);
    }
  };

  // Game functions
  const createRoom = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/rooms`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      const data = await response.json();
      setRoomId(data.room_id);
      await joinRoom(data.room_id);
    } catch (error) {
      console.error('Error creating room:', error);
    }
  };

  const joinRoom = async (roomIdToJoin = roomId) => {
    try {
      const playerId = `player_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      
      console.log('Joining room:', roomIdToJoin, 'as player:', playerId);
      
      const response = await fetch(`${BACKEND_URL}/api/rooms/${roomIdToJoin}/join`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          player_id: playerId,
          name: `Player ${playerId.slice(-4)}`
        }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to join room');
      }
      
      const data = await response.json();
      console.log('Join room response:', data);
      
      setPlayerInfo(data);
      setGameState('playing');
      
      // Immediately fetch board state via REST API
      console.log('Fetching initial board state...');
      await fetchBoardState(roomIdToJoin);
      
      // Try to connect WebSocket (but don't depend on it)
      try {
        connectWebSocket(roomIdToJoin, playerId);
      } catch (wsError) {
        console.warn('WebSocket connection failed, using REST API fallback:', wsError);
        // Set up periodic polling as fallback
        const pollInterval = setInterval(async () => {
          if (gameState === 'playing') {
            try {
              await fetchBoardState(roomIdToJoin);
            } catch (error) {
              console.error('Error in polling:', error);
            }
          } else {
            clearInterval(pollInterval);
          }
        }, 2000);
      }
      
      // Initialize WebRTC
      await initializeWebRTC();
      
    } catch (error) {
      console.error('Error joining room:', error);
    }
  };

  const makeMove = (fromSquare, toSquare) => {
    const piece = board[fromSquare];
    console.log('Attempting move:', fromSquare, 'to', toSquare, 'piece:', piece);
    
    if (!piece || !piece.startsWith(playerInfo?.color) || currentTurn !== playerInfo?.color) {
      console.log('Move rejected - not your turn or piece');
      return false;
    }
    
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      console.log('Sending move via WebSocket');
      wsRef.current.send(JSON.stringify({
        type: 'move',
        from_square: fromSquare,
        to_square: toSquare,
        piece: piece,
        player_color: playerInfo?.color
      }));
    } else {
      console.log('WebSocket not available, move not sent');
    }
    return true;
  };

  const handleSquareClick = (square) => {
    console.log('Square clicked:', square, 'selected:', selectedSquare);
    
    if (selectedSquare && selectedSquare !== square) {
      if (makeMove(selectedSquare, square)) {
        setSelectedSquare(null);
      }
    } else {
      setSelectedSquare(square);
    }
  };

  const handleDragStart = (e, square) => {
    const piece = board[square];
    if (piece && piece.startsWith(playerInfo?.color) && currentTurn === playerInfo?.color) {
      setDraggedPiece({ square, piece });
      e.dataTransfer.effectAllowed = 'move';
    } else {
      e.preventDefault();
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e, targetSquare) => {
    e.preventDefault();
    if (draggedPiece && draggedPiece.square !== targetSquare) {
      makeMove(draggedPiece.square, targetSquare);
    }
    setDraggedPiece(null);
  };

  const toggleMute = () => {
    if (localStreamRef.current) {
      const audioTracks = localStreamRef.current.getAudioTracks();
      audioTracks.forEach(track => {
        track.enabled = isMuted;
      });
      setIsMuted(!isMuted);
    }
  };

  const resignGame = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'game_action',
        action: 'resign'
      }));
    }
  };

  const requestUndo = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'game_action',
        action: 'undo_request'
      }));
    }
  };

  const requestRematch = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'game_action',
        action: 'rematch_request'
      }));
    }
  };

  const copyRoomId = () => {
    if (playerInfo?.room_id) {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(playerInfo.room_id).then(() => {
          setShowRoomShare(true);
          setTimeout(() => setShowRoomShare(false), 2000);
        }).catch(() => {
          // Fallback for older browsers
          const textArea = document.createElement('textarea');
          textArea.value = playerInfo.room_id;
          document.body.appendChild(textArea);
          textArea.select();
          document.execCommand('copy');
          document.body.removeChild(textArea);
          setShowRoomShare(true);
          setTimeout(() => setShowRoomShare(false), 2000);
        });
      }
    }
  };

  const renderSquare = (file, rank) => {
    const square = file + rank;
    const piece = board[square];
    const isLight = (files.indexOf(file) + parseInt(rank)) % 2 === 0;
    const isSelected = selectedSquare === square;
    const isValidMoveTarget = selectedSquare && selectedSquare !== square && board[selectedSquare]?.startsWith(playerInfo?.color);

    return (
      <div
        key={square}
        className={`chess-square ${isLight ? 'light' : 'dark'} ${isSelected ? 'selected' : ''} ${isValidMoveTarget ? 'valid-target' : ''}`}
        onClick={() => handleSquareClick(square)}
        onDragOver={handleDragOver}
        onDrop={(e) => handleDrop(e, square)}
      >
        {piece && (
          <div
            className="chess-piece"
            data-piece={piece}
            draggable={piece.startsWith(playerInfo?.color) && currentTurn === playerInfo?.color}
            onDragStart={(e) => handleDragStart(e, square)}
          >
            {PIECE_SYMBOLS[piece]}
          </div>
        )}
        <div className="square-label">{square}</div>
      </div>
    );
  };

  if (gameState === 'menu') {
    return (
      <div className="App">
        <div className="menu-container">
          <h1 className="game-title">3D Chess Multiplayer</h1>
          <div className="menu-buttons">
            <button className="menu-btn create-btn" onClick={createRoom}>
              Create Room
            </button>
            <div className="join-room">
              <input
                type="text"
                placeholder="Enter Room ID"
                value={roomId}
                onChange={(e) => setRoomId(e.target.value)}
                className="room-input"
              />
              <button 
                className="menu-btn join-btn" 
                onClick={() => joinRoom()}
                disabled={!roomId.trim()}
              >
                Join Room
              </button>
            </div>
          </div>
          <div className="features-list">
            <h3>Features:</h3>
            <ul>
              <li>✓ Real-time multiplayer (WebSocket + REST fallback)</li>
              <li>✓ 3D chess pieces with drag & drop</li>
              <li>✓ Voice chat with WebRTC</li>
              <li>✓ Complete chess rules validation</li>
              <li>✓ Resign, undo & rematch options</li>
              <li>✓ Room sharing</li>
            </ul>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="App">
      <div className="game-container">
        <div className="game-header">
          <div className="game-info">
            <h2>Room: {playerInfo?.room_id}</h2>
            <button className="share-btn" onClick={copyRoomId}>
              {showRoomShare ? '✓ Copied!' : '📋 Share Room'}
            </button>
            <div className="player-info">
              <span className={`player-color ${playerInfo?.color}`}>
                You are playing as {playerInfo?.color}
              </span>
              <span className={`turn-indicator ${currentTurn === playerInfo?.color ? 'your-turn' : ''}`}>
                {currentTurn === playerInfo?.color ? "Your Turn" : "Opponent's Turn"}
              </span>
            </div>
            {(player1Name || player2Name) && (
              <div className="players-names">
                <span>White: {player1Name || 'Waiting...'}</span>
                <span>Black: {player2Name || 'Waiting...'}</span>
              </div>
            )}
          </div>
          
          <div className="controls-panel">
            <div className="status-indicators">
              <div className={`connection-status ${connectionStatus}`}>
                Connection: {connectionStatus}
              </div>
              <div className={`voice-status ${voiceConnected ? 'connected' : 'disconnected'}`}>
                Voice: {voiceConnected ? 'Connected' : 'Disconnected'}
              </div>
            </div>
            
            <div className="voice-controls">
              <button 
                className="voice-btn"
                onClick={startVoiceCall}
                disabled={!peerConnectionRef.current}
              >
                Start Voice Chat
              </button>
              <button 
                className={`mute-btn ${isMuted ? 'muted' : ''}`}
                onClick={toggleMute}
              >
                {isMuted ? '🔇' : '🔊'}
              </button>
            </div>

            <div className="game-actions">
              <button 
                className="action-btn refresh-btn" 
                onClick={() => fetchBoardState()}
              >
                🔄 Refresh Board
              </button>
              <button className="action-btn resign-btn" onClick={resignGame}>
                Resign
              </button>
              <button 
                className="action-btn undo-btn" 
                onClick={requestUndo}
                disabled={moveHistory.length === 0}
              >
                Request Undo {undoRequests.length > 0 && `(${undoRequests.length})`}
              </button>
              <button 
                className="action-btn rematch-btn" 
                onClick={requestRematch}
                disabled={gameStatus === 'active'}
              >
                Rematch {rematchRequests.length > 0 && `(${rematchRequests.length})`}
              </button>
            </div>
          </div>
        </div>

        {invalidMoveMessage && (
          <div className="invalid-move-message">
            Invalid move: {invalidMoveMessage}
          </div>
        )}

        <div className="chess-board-container">
          <div className="chess-board">
            {ranks.map(rank => 
              files.map(file => renderSquare(file, rank))
            )}
          </div>
        </div>

        <div className="game-status">
          <p>Game Status: {gameStatus}</p>
          {gameStatus === 'waiting' && <p>Waiting for opponent to join...</p>}
          {gameStatus === 'resigned' && <p>Game ended by resignation. Winner: {winner}</p>}
          {winner && <p className="winner-announcement">🎉 {winner} wins!</p>}
          
          <div className="debug-info">
            <p><strong>Debug Info:</strong> Board has {Object.keys(board).length} pieces | Room: {playerInfo?.room_id} | Player: {playerInfo?.color}</p>
            {Object.keys(board).length === 0 && (
              <p className="debug-warning">⚠️ No chess pieces loaded! The game will start when both players join.</p>
            )}
          </div>
          
          <div className="move-history">
            <h4>Move History:</h4>
            <div className="moves-list">
              {moveHistory.slice(-5).map((move, index) => (
                <div key={index} className="move-item">
                  {PIECE_SYMBOLS[move.piece]} {move.from} → {move.to}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      
      <audio ref={remoteAudioRef} autoPlay />
    </div>
  );
}

export default App;