# VitalLink — Real-Time Emergency Dashboard

A real-time hospital emergency dashboard built with React + Vite + Tailwind CSS.
Connects to a live AWS API Gateway WebSocket and displays incoming ambulance vitals with no page refresh.

---

## 🚀 Getting Started

### Prerequisites
- Node.js 18+
- npm 9+

### Install & Run

```bash
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

### Build for Production

```bash
npm run build
npm run preview
```

---

## 🔌 WebSocket Configuration

The WebSocket URL is defined in a single place:

```
src/utils/config.js
```

```js
export const WS_URL = 'wss://018nlv643l.execute-api.eu-north-1.amazonaws.com/production/'
```

Change `WS_URL` here to point to a different WebSocket endpoint.

---

## 📁 Project Structure

```
vitallink/
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
└── src/
    ├── main.jsx              # React entry point
    ├── App.jsx               # Root component, page routing
    ├── index.css             # Tailwind directives + global styles
    ├── components/
    │   ├── Sidebar.jsx       # Left nav sidebar with connection status
    │   ├── AmbulanceCard.jsx # Individual ambulance card
    │   ├── VitalStat.jsx     # Single vital sign with abnormal highlight
    │   ├── ConnectionBanner.jsx # Top banner for disconnected state
    │   ├── EmptyState.jsx    # Shown when no ambulances active
    │   └── PlaceholderPage.jsx # Stub for non-functional nav pages
    ├── hooks/
    │   └── useWebSocket.js   # WebSocket hook with auto-reconnect
    ├── pages/
    │   └── DashboardPage.jsx # Main ambulance feed page
    └── utils/
        ├── config.js         # ← WebSocket URL lives here
        └── vitals.js         # Priority/status colors, abnormal ranges
```

---

## 🎨 Design

- Dark theme (`#0a0a0f` background)
- Red primary accent (`#e8352a`)
- Left vertical sidebar navigation
- Priority-colored card borders (Red = High, Orange = Medium)
- Vitals flash red on update if abnormal
- IBM Plex Sans + IBM Plex Mono typography

---

## ⚡ WebSocket Behaviour

| Event | Behaviour |
|---|---|
| New `ambulance_id` | Creates a new card |
| Same `ambulance_id` | Updates vitals in place (no new card) |
| Connection drop | Auto-reconnects every 3s, up to 10 attempts |
| Reconnecting | Yellow banner + sidebar indicator |
| Disconnected | Red banner |

---

## 📦 Tech Stack

- React 18 (Vite)
- Tailwind CSS 3
- No external state library (useReducer + hooks)
- No authentication
- No backend code

---

## 🚫 Not Included

- Authentication / login
- DynamoDB or any database
- REST API calls
- Role management
