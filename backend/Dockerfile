# 后端镜像：两段构建（先 Maven 打 fat jar，再只带 JRE 运行）
#
# 为什么分两段：Maven + JDK 加起来 700MB 上下，而运行只需要一个 JRE。
# 最终镜像小一半以上，也少了整整一套构建工具（供应链面更小）。

# ---------- 构建段 ----------
# 构建段用 Maven 镜像自带的仓库，不引 .m2repo（那是本机沙箱的权宜之计，见 README「沙箱坑」）
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build

# 先把 pom 单独拷进来下依赖：源码改了不会让这一层失效，重建时能命中缓存
COPY pom.xml .
RUN mvn -q -B dependency:go-offline

COPY src ./src
# 跳过测试：镜像构建只负责"能跑起来"，测试由 CI / 本地 mvn test 负责。
# （在构建镜像时跑测试会让构建慢十几倍，而且失败原因常常是环境而不是代码。）
RUN mvn -q -B -DskipTests package

# ---------- 运行段 ----------
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app

# 不用 root 跑：容器里拿到 root 没有任何好处，只会在出事时放大影响
RUN addgroup -S dailyseed && adduser -S dailyseed -G dailyseed
COPY --from=build --chown=dailyseed:dailyseed /build/target/*.jar app.jar
USER dailyseed

EXPOSE 8080

# 健康检查直接问应用自己的 /api/health（它同时看库、迁移、种子、时钟）。
# 用它而不是只看端口：端口开着但库连不上时，服务其实是不能用的。
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/api/health >/dev/null 2>&1 || exit 1

# MaxRAMPercentage：让 JVM 跟着容器内存上限走，而不是看着宿主机的内存去开堆
ENV JAVA_OPTS="-XX:MaxRAMPercentage=75 -XX:+ExitOnOutOfMemoryError"
ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /app/app.jar"]
