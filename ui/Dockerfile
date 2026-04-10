FROM node:20-alpine AS deps

WORKDIR /app

COPY ui/package.json ui/yarn.lock ./
RUN yarn install --non-interactive

FROM node:20-alpine AS builder

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY ui/ ./

RUN yarn build > /tmp/next-build.log 2>&1 \
    || (cat /tmp/next-build.log | tr -cd '\11\12\15\40-\176' && exit 1) \
    && cat /tmp/next-build.log | tr -cd '\11\12\15\40-\176'

FROM node:20-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV BATTERY_LAB_PYTHON=/usr/bin/python3

RUN apk add --no-cache python3 py3-reportlab font-dejavu

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY data/kb/equipment_rules.json ./data/kb/equipment_rules.json
COPY data/reference/equipment_manuals/manual_index.json ./data/reference/equipment_manuals/manual_index.json
COPY scripts/render_experiment_plan_pdf.py ./scripts/render_experiment_plan_pdf.py

EXPOSE 3000

CMD ["node", "server.js"]
