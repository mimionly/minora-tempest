#!/bin/bash

# Define paths
BACKEND_DIR="./flood"
FRONTEND_DIR="./flood-routing/ui"

echo "Cleaning up old ports..."
fuser -k 5000/tcp 2>/dev/null
fuser -k 8081/tcp 2>/dev/null

echo "Starting Python Backend on port 5000..."
cd $BACKEND_DIR
python3 app.py &
BACKEND_PID=$!

echo "Starting React Native Web Frontend on port 8081..."
cd ../$FRONTEND_DIR
npm run web &
FRONTEND_PID=$!

echo "========================================="
echo "FloodRoute System is Booting Up!"
echo "Frontend available at: http://localhost:8081/explore"
echo "Backend available at:  http://localhost:5000"
echo "Press Ctrl+C to stop both servers."
echo "========================================="

# Handle shutdown gracefully
trap "echo 'Shutting down...'; kill $BACKEND_PID $FRONTEND_PID; exit" SIGINT SIGTERM

wait $BACKEND_PID $FRONTEND_PID
