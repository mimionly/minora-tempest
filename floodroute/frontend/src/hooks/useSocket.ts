import { useEffect, useRef } from "react";
import { io, Socket } from "socket.io-client";

export function useSocket() {
  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    const socket = io("http://localhost:4000", { transports: ["websocket"] });
    socketRef.current = socket;
    return () => {
      socket.disconnect();
    };
  }, []);

  return socketRef;
}