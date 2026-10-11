# 前端镜像：Node 构建出 dist，再交给 nginx 当静态站点（外加把 /api 反代到后端）
#
# 为什么用 nginx 而不是 `vite preview`：preview 是开发工具，不设缓存头、不做 gzip、
# 也不会优雅处理 SPA 回退。上线要的是稳，不是方便。

# ---------- 构建段 ----------
FROM node:22-alpine AS build
WORKDIR /build

COPY package.json package-lock.json ./
# 用 npm ci 而不是 install：它严格按 lock 文件装，构建才是可复现的
RUN npm ci --ignore-scripts

COPY . .
RUN npm run build

# ---------- 运行段 ----------
FROM nginx:1.27-alpine
COPY --from=build /build/dist /usr/share/nginx/html

# ⚠️ 放进 templates/：官方镜像启动时会用 envsubst 渲染它，生成 /etc/nginx/conf.d/default.conf，
#    这样后端地址就能从环境变量传进来（同一个镜像可以指向不同后端）。
#    Nginx 官方镜像默认只对 templates/ 做 envsubst，并且会保留 $host 这类运行时变量。
COPY deploy/templates/default.conf.template /etc/nginx/templates/default.conf.template
ENV BACKEND_UPSTREAM=http://127.0.0.1:8080

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/manifest.webmanifest >/dev/null 2>&1 || exit 1
