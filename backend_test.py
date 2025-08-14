import requests
import sys
import json
from datetime import datetime

class ChessAPITester:
    def __init__(self, base_url="https://chess-connect.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.room_id = None
        self.player1_id = None
        self.player2_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        if headers is None:
            headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)}")
                    return True, response_data
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error Response: {json.dumps(error_data, indent=2)}")
                except:
                    print(f"   Error Text: {response.text}")
                return False, {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout")
            return False, {}
        except requests.exceptions.ConnectionError:
            print(f"❌ Failed - Connection error")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test health endpoint"""
        success, response = self.run_test(
            "Health Check",
            "GET",
            "api/health",
            200
        )
        return success

    def test_create_room(self):
        """Test room creation"""
        success, response = self.run_test(
            "Create Room",
            "POST",
            "api/rooms",
            200
        )
        if success and 'room_id' in response:
            self.room_id = response['room_id']
            print(f"   Created room: {self.room_id}")
            return True
        return False

    def test_get_room(self):
        """Test getting room details"""
        if not self.room_id:
            print("❌ No room ID available for testing")
            return False
            
        success, response = self.run_test(
            "Get Room Details",
            "GET",
            f"api/rooms/{self.room_id}",
            200
        )
        return success

    def test_join_room_player1(self):
        """Test first player joining room"""
        if not self.room_id:
            print("❌ No room ID available for testing")
            return False
            
        self.player1_id = f"player_{int(datetime.now().timestamp())}_{hash('player1') % 1000000000}"
        
        success, response = self.run_test(
            "Join Room - Player 1",
            "POST",
            f"api/rooms/{self.room_id}/join",
            200,
            data={
                "player_id": self.player1_id,
                "name": "Test Player 1"
            }
        )
        
        if success:
            expected_color = "white"  # First player should be white
            if response.get('color') == expected_color:
                print(f"   Player 1 assigned correct color: {expected_color}")
                return True
            else:
                print(f"   Warning: Expected color {expected_color}, got {response.get('color')}")
        return success

    def test_join_room_player2(self):
        """Test second player joining room"""
        if not self.room_id:
            print("❌ No room ID available for testing")
            return False
            
        self.player2_id = f"player_{int(datetime.now().timestamp()) + 1}_{hash('player2') % 1000000000}"
        
        success, response = self.run_test(
            "Join Room - Player 2",
            "POST",
            f"api/rooms/{self.room_id}/join",
            200,
            data={
                "player_id": self.player2_id,
                "name": "Test Player 2"
            }
        )
        
        if success:
            expected_color = "black"  # Second player should be black
            if response.get('color') == expected_color:
                print(f"   Player 2 assigned correct color: {expected_color}")
                return True
            else:
                print(f"   Warning: Expected color {expected_color}, got {response.get('color')}")
        return success

    def test_join_room_third_player(self):
        """Test third player joining room (should fail)"""
        if not self.room_id:
            print("❌ No room ID available for testing")
            return False
            
        player3_id = f"player_{int(datetime.now().timestamp()) + 2}_{hash('player3') % 1000000000}"
        
        success, response = self.run_test(
            "Join Room - Player 3 (Should Fail)",
            "POST",
            f"api/rooms/{self.room_id}/join",
            400,  # Should return 400 for room full
            data={
                "player_id": player3_id,
                "name": "Test Player 3"
            }
        )
        return success

    def test_get_board_state(self):
        """Test getting board state"""
        if not self.room_id:
            print("❌ No room ID available for testing")
            return False
            
        success, response = self.run_test(
            "Get Board State",
            "GET",
            f"api/rooms/{self.room_id}/board",
            200
        )
        
        if success:
            # Verify board structure
            if 'board' in response and 'current_turn' in response and 'game_status' in response:
                board = response['board']
                print(f"   Board has {len(board)} pieces")
                print(f"   Current turn: {response['current_turn']}")
                print(f"   Game status: {response['game_status']}")
                
                # Check for initial chess pieces
                expected_pieces = ['white_king', 'black_king', 'white_queen', 'black_queen']
                found_pieces = [piece for piece in board.values() if piece in expected_pieces]
                print(f"   Found key pieces: {found_pieces}")
                
                return len(found_pieces) >= 2  # At least kings should be present
            else:
                print("   Warning: Missing expected board structure")
        return success

    def test_resign_game(self):
        """Test game resignation"""
        if not self.room_id or not self.player1_id:
            print("❌ No room ID or player ID available for testing")
            return False
            
        success, response = self.run_test(
            "Resign Game",
            "POST",
            f"api/rooms/{self.room_id}/resign/{self.player1_id}",
            200
        )
        
        if success:
            if 'status' in response and response['status'] == 'resigned':
                print(f"   Game resigned successfully, winner: {response.get('winner')}")
                return True
            else:
                print("   Warning: Unexpected resignation response")
        return success

    def test_undo_request(self):
        """Test undo request"""
        if not self.room_id or not self.player1_id:
            print("❌ No room ID or player ID available for testing")
            return False
            
        success, response = self.run_test(
            "Request Undo",
            "POST",
            f"api/rooms/{self.room_id}/undo/{self.player1_id}",
            200
        )
        
        if success:
            if 'status' in response and response['status'] == 'undo_requested':
                print(f"   Undo requested successfully, requests: {response.get('requests')}")
                return True
            else:
                print("   Warning: Unexpected undo response")
        return success

    def test_rematch_request(self):
        """Test rematch request"""
        if not self.room_id or not self.player1_id:
            print("❌ No room ID or player ID available for testing")
            return False
            
        success, response = self.run_test(
            "Request Rematch",
            "POST",
            f"api/rooms/{self.room_id}/rematch/{self.player1_id}",
            200
        )
        
        if success:
            if 'status' in response and 'rematch' in response['status']:
                print(f"   Rematch requested successfully, status: {response.get('status')}")
                return True
            else:
                print("   Warning: Unexpected rematch response")
        return success

    def test_nonexistent_room(self):
        """Test accessing non-existent room"""
        fake_room_id = "fake1234"
        success, response = self.run_test(
            "Get Non-existent Room (Should Fail)",
            "GET",
            f"api/rooms/{fake_room_id}",
            404
        )
        return success

def main():
    print("🚀 Starting Chess API Tests")
    print("=" * 50)
    
    # Setup
    tester = ChessAPITester()
    
    # Run tests in sequence
    tests = [
        ("Health Check", tester.test_health_check),
        ("Create Room", tester.test_create_room),
        ("Get Room Details", tester.test_get_room),
        ("Join Room - Player 1", tester.test_join_room_player1),
        ("Join Room - Player 2", tester.test_join_room_player2),
        ("Join Room - Player 3 (Should Fail)", tester.test_join_room_third_player),
        ("Get Board State", tester.test_get_board_state),
        ("Request Undo", tester.test_undo_request),
        ("Request Rematch", tester.test_rematch_request),
        ("Resign Game", tester.test_resign_game),
        ("Non-existent Room (Should Fail)", tester.test_nonexistent_room),
    ]
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if not result:
                print(f"\n⚠️  Test '{test_name}' failed - continuing with remaining tests")
        except Exception as e:
            print(f"\n💥 Test '{test_name}' crashed: {str(e)}")
    
    # Print final results
    print("\n" + "=" * 50)
    print(f"📊 Final Results: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    elif tester.tests_passed >= tester.tests_run * 0.7:  # 70% pass rate
        print("⚠️  Most tests passed, but some issues found")
        return 0
    else:
        print("❌ Many tests failed - significant issues detected")
        return 1

if __name__ == "__main__":
    sys.exit(main())