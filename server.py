#! python -u server.py
from flask import Flask
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app)

@app.route('/')
def index():
    return "Server is running."

@socketio.on('transcription')
def handle_transcription(data):
    # Broadcast the transcription to all connected clients
    print(data)
    emit('transcription', data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)