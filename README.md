# Trading Platform Application

A real-time trading platform dashboard built with React (Vite) and Express.

## Prerequisites

Before running the application, ensure you have the following installed:
- [Node.js](https://nodejs.org/) (v18 or higher recommended)
- npm (Node Package Manager)

## Installation

1. Navigate to the project directory:
   ```bash
   cd TradingPlatform
   ```
2. Install the dependencies:
   ```bash
   npm install
   ```

## Running the Application

To start both the backend server and the frontend client simultaneously, run:

```bash
npm run dev
```

- **Backend**: Runs on `http://localhost:3000`
- **Frontend**: Typically runs on `http://localhost:5173` (check your terminal for the exact URL).

Open your browser and navigate to the frontend URL to view the application.

## Project Structure

- `src/`: Frontend React source code.
- `server/`: Backend Express server code.
- `package.json`: Project configuration and scripts.

---

# React + Vite (Original Template README)

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) (or [oxc](https://oxc.rs) when used in [rolldown-vite](https://vite.dev/guide/rolldown)) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.

## 🚀 NSE Volume Spike Radar

A high-performance intraday scanner to identify stocks with significant volume surges (Current 5-min Volume > 2x of 5-Day Average).

### 🛠 Setup
1. **Install Requirements**:
   ```bash
   pip3 install -r requirements.txt
   ```

### 🖥 Web Interface (Recommended)
The tool includes a premium Glassmorphic web dashboard with real-time progress tracking.
1. **Start the Server**:
   ```bash
   python3 app.py
   ```
2. **Access UI**:
   Open [http://localhost:8083](http://localhost:8083) in your browser.

### 📜 CLI Mode
For quick terminal-based analysis:
```bash
python3 analyze_volume.py
```

### ⚙️ Features
- **Smart Filtering**: Automatically ignores illiquid stocks (< ₹5L turnover) to reduce noise.
- **Auto-Symbol Fetching**: Dynamically fetches all 2200+ NSE symbols.
- **Performance Optimized**: Uses batch processing and multi-threaded downloads via `yfinance`.
- **Visual Intensity**: The UI color-codes results based on the spike magnitude.

---

## 🌐 Deployment & Hosting

The application is structured as a React frontend with two backend options (Node.js and Python).

### Frontend (GitHub Pages)
The React frontend is automatically deployed to GitHub Pages via GitHub Actions when you push to the `main` branch.
- **Live URL**: `https://TechyShahid.github.io/TradingPlatform/`

### Backend Hosting
Since GitHub Pages only hosts static content, you must host your backend on a service like **Render**, **Railway**, or **Heroku**.

#### 1. Node.js Backend (Recommended)
1. Sign up for [Render](https://render.com/).
2. Create a new **Web Service** and connect this repository.
3. Use the following settings:
   - **Environment**: `Node`
   - **Build Command**: `npm install`
   - **Start Command**: `node server/index.js`
4. Set the `PORT` environment variable to `3000`.

#### 2. Python Backend
1. Sign up for **Render**.
2. Create a new **Web Service**.
3. Use the following settings:
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`

#### 3. Connecting Frontend to Backend
Once your backend is live, update the `VITE_API_URL` environment variable in your GitHub repository secrets (or in your build command) to point to your backend URL:
- Go to Repository **Settings** > **Secrets and variables** > **Actions**.
- Add a new repository variable: `VITE_API_URL` = `https://your-backend-url.onrender.com/api`
