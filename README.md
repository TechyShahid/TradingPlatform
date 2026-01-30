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
