# Vercel Frontend + Aliyun Backend

## Goal

Use Vercel to host the Next.js frontend over HTTPS, while keeping the Flask backend on Aliyun ECS.

This solves:

- public HTTPS page access
- camera permissions in the browser
- avoiding direct browser requests to `http://<ecs-ip>:5000`

## Vercel Project Settings

Create a Vercel project from the `frontend` directory.

Set these environment variables in Vercel:

```env
NEXT_PUBLIC_BACKEND_URL=/backend-proxy
PUBLIC_SITE_URL=https://<your-project>.vercel.app
AUTH_LOGIN_EMAIL=admin@panelmind.cn
AUTH_LOGIN_PASSWORD=your-password
AUTH_LOGIN_NAME=PanelMind 管理员
VERCEL_BACKEND_ORIGIN=http://182.92.78.45:5000
```

Notes:

- `NEXT_PUBLIC_BACKEND_URL=/backend-proxy` makes the browser call same-origin HTTPS paths like `/backend-proxy/api/...`
- `VERCEL_BACKEND_ORIGIN` is only used by Next rewrites on the server side
- keep the Aliyun backend reachable from the public internet on port `5000`

## How Proxying Works

The frontend now expects:

- API calls: `/backend-proxy/api/...`
- Socket.IO: `/backend-proxy/socket.io/...`

`frontend/next.config.js` rewrites those requests to:

- `http://182.92.78.45:5000/api/...`
- `http://182.92.78.45:5000/socket.io/...`

## Aliyun Requirements

Make sure the ECS security group allows:

- `5000/tcp`

The backend must be running and reachable at:

```text
http://182.92.78.45:5000/health
```

## After Deployment

Open the Vercel URL, for example:

```text
https://<your-project>.vercel.app
```

Then verify:

- login works
- dashboard loads data
- camera access prompt appears
- live interview can connect to Socket.IO
