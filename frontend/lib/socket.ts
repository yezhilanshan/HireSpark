/**
 * Socket.IO 客户端封装
 */
import { io, Socket } from 'socket.io-client';

const DEFAULT_SOCKET_PORT = '5000';

const getSocketUrl = (): string => {
    const envUrl = process.env.NEXT_PUBLIC_BACKEND_URL?.trim();
    if (envUrl) {
        return envUrl.replace(/\/$/, '');
    }

    if (typeof window !== 'undefined') {
        const { protocol, hostname } = window.location;
        return `${protocol}//${hostname}:${DEFAULT_SOCKET_PORT}`;
    }

    return `http://localhost:${DEFAULT_SOCKET_PORT}`;
};

class SocketClient {
    private socket: Socket | null = null;
    private static instance: SocketClient;
    private connectPromise: Promise<void> | null = null;

    private constructor() { }

    static getInstance(): SocketClient {
        if (!SocketClient.instance) {
            SocketClient.instance = new SocketClient();
        }
        return SocketClient.instance;
    }

    connect(): Promise<void> {
        if (this.socket?.connected) {
            return Promise.resolve();
        }

        if (this.connectPromise) {
            return this.connectPromise;
        }

        const socketUrl = getSocketUrl();

        const connectWithTransports = (transports: Array<'websocket' | 'polling'>): Promise<void> => {
            return new Promise((resolve, reject) => {
                this.socket?.disconnect();

                this.socket = io(socketUrl, {
                    transports,
                    upgrade: true,
                    reconnection: true,
                    reconnectionAttempts: Infinity,
                    reconnectionDelay: 1000,
                    reconnectionDelayMax: 5000,
                    timeout: 8000,
                });

                this.socket.once('connect', () => {
                    console.log(`Connected to server via ${transports.join(', ')}`);
                    resolve();
                });

                this.socket.once('connect_error', (error) => {
                    console.error(`Connection error with transports [${transports.join(', ')}]:`, error);
                    this.socket?.disconnect();
                    reject(error);
                });

                this.socket.on('disconnect', () => {
                    console.log('Disconnected from server');
                });
            });
        };

        // 使用 polling 起连再升级到 websocket，避免在 Werkzeug 开发服务器上 websocket 强连导致 500。
        this.connectPromise = connectWithTransports(['polling', 'websocket'])
            .catch((mixedError) => {
                console.warn('Mixed transport connection failed, retry with polling only.');
                return connectWithTransports(['polling']).catch(() => {
                    throw mixedError;
                });
            })
            .finally(() => {
                this.connectPromise = null;
            });

        return this.connectPromise;
    }

    disconnect(): void {
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
        }
    }

    emit(event: string, data?: any): void {
        if (this.socket) {
            this.socket.emit(event, data);
        } else {
            console.error('Socket not connected');
        }
    }

    on(event: string, callback: (data: any) => void): void {
        if (this.socket) {
            this.socket.on(event, callback);
        }
    }

    off(event: string, callback?: (data: any) => void): void {
        if (this.socket) {
            if (callback) {
                this.socket.off(event, callback);
            } else {
                this.socket.off(event);
            }
        }
    }

    isConnected(): boolean {
        return this.socket?.connected || false;
    }
}

export default SocketClient;
