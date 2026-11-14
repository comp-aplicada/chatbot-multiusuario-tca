# Front-end

Interface de chat em React + Vite + TypeScript. Plano completo em [`docs/plano-frontend.md`](../docs/plano-frontend.md).

## Requisitos

- Node 20 ou mais novo

## Como rodar

```bash
cd frontend
npm install
npm run dev
```

Abre em `http://localhost:5173`. As chamadas para `/api` vão para `http://localhost:8000` pelo proxy do Vite, então o backend precisa estar rodando nessa porta.

## Scripts

| Comando | O que faz |
|---|---|
| `npm run dev` | Servidor de desenvolvimento |
| `npm run build` | Checa os tipos e gera o build estático em `dist/` |
| `npm run typecheck` | Só checa os tipos (TypeScript) |
| `npm run preview` | Serve o `dist/` localmente |
| `npm test` | Roda os testes uma vez (Vitest) |
| `npm run test:watch` | Roda os testes em modo watch |
| `npm run lint` | Lint com oxlint |
