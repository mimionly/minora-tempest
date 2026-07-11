import { Server as SocketServer } from "socket.io";
import { Server as HttpServer } from "http";
import { logger } from "../utils/logger";

export function attachSocket(httpServer: HttpServer): SocketServer {
  const io = new SocketServer(httpServer, { cors: { origin: "*" } });

  io.on("connection", (socket) => {
    logger.info(`Client connected: ${socket.id}`);
    socket.on("disconnect", () => logger.info(`Client disconnected: ${socket.id}`));
  });

  return io;
}