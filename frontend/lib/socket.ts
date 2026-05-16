/**
 * Socket.IO 客户端封装
 */
import { io, Socket } from 'socket.io-client';
import { getBackendBaseUrl } from './backend';

type SocketTarget = {
    url?: string
    path: string
}

const trimTrailingSlash = (value: string): string => value.replace(/\/+$/, '')

const getSocketTarget = (): SocketTarget => {
    // Direct Socket.IO URL takes priority (bypasses Vercel proxy for long-lived connections)
    const directSocketUrl = process.env.NEXT_PUBLIC_SOCKET_URL
    if (directSocketUrl) {
        try {
            const parsed = new URL(directSocketUrl)
            const basePath = trimTrailingSlash(parsed.pathname || '')
            return {
                url: `${parsed.protocol}//${parsed.host}`,
                path: `${basePath || ''}/socket.io`,
            }
        } catch {
            // fall through
        }
    }

    const backendBaseUrl = trimTrailingSlash(getBackendBaseUrl())

    if (!backendBaseUrl) {
        return { path: '/socket.io' }
    }

    if (backendBaseUrl.startsWith('/')) {
        return {
            path: `${backendBaseUrl}/socket.io`,
        }
    }

    try {
        const parsed = new URL(backendBaseUrl)
        const basePath = trimTrailingSlash(parsed.pathname || '')
        return {
            url: `${parsed.protocol}//${parsed.host}`,
            path: `${basePath || ''}/socket.io`,
        }
    } catch {
        return { path: '/socket.io' }
    }
}

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

        const socketTarget = getSocketTarget();

        const connectWithTransports = (transports: Array<'websocket' | 'polling'>): Promise<void> => {
            return new Promise((resolve, reject) => {
                this.socket?.disconnect();

                this.socket = io(socketTarget.url, {
                    path: socketTarget.path,
                    transports,
                    upgrade: true,
                    // Initial connection is controlled by this Promise. Let the page show a
                    // clear backend-unavailable error instead of Socket.IO retrying forever.
                    reconnection: false,
                    timeout: 4000,
                });

                this.socket.once('connect', () => {
                    console.log(`Connected to server via ${transports.join(', ')}`);
                    resolve();
                });

                this.socket.io.engine.once('upgrade', (transport) => {
                    console.log(`Socket transport upgraded to ${transport.name}`);
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

        // Start with polling and let Socket.IO upgrade to WebSocket when the backend supports it.
        this.connectPromise = connectWithTransports(['polling', 'websocket'])
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
