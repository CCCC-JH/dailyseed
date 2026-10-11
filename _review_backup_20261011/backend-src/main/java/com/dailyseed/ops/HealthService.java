package com.dailyseed.ops;

import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import javax.sql.DataSource;
import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.MigrationInfo;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;

/**
 * 「这台服务现在到底是什么状态」——一条请求就能回答。
 *
 * <p>为什么需要它：这套东西是**匿名、无推送、无账号**的，出问题时没有任何用户会来报错，
 * 你也不会在日志里看到"某某打不开"。所以必须有一个**不需要身份**的入口，
 * 让"服务到底活着吗、库连上了吗、迁移跑完了吗、种子灌进去了吗"能一句话问清楚。
 *
 * <p>两个刻意的设计：
 * <ol>
 *   <li><b>它不需要 {@code X-Device-Id}</b>。健康检查不该先要求一个身份——
 *       那会让"身份系统坏了"连带把"我能不能知道身份系统坏了"也一起弄坏</li>
 *   <li><b>它是 readiness，不是 liveness</b>：库连不上就返回 <b>503</b>，
 *       而不是回 200 加一行"db: down"。让编排系统（compose / systemd / 负载均衡）
 *       自己去判断该不该把流量打过来，而不是让每个调用方自己解释字符串</li>
 * </ol>
 */
@Service
public class HealthService {

    /** 卡片库应该是这个数（`tools/gen_seed.py` 校验的那个数，这里再守一道） */
    private static final int EXPECTED_CARDS = 100;

    /** 卡片少于这个数就算种子没灌好。不写死 100 是为了容忍以后加卡，但空库一定要报出来 */
    private static final int MIN_CARDS = 1;

    private final JdbcClient jdbc;
    private final DataSource dataSource;
    private final Flyway flyway;
    private final ActivityCounters counters;
    private final int maxDrawsPerDay;
    private final boolean cookieEnabled;
    private final boolean cookieSecure;
    private final boolean devMode;
    private final Instant startedAt = Instant.now();

    /** 上一次探测失败的原因。留着它，不然"503"是个没有信息量的答案 */
    private final AtomicReference<String> lastFailure = new AtomicReference<>(null);

    public HealthService(JdbcClient jdbc, DataSource dataSource, Flyway flyway, ActivityCounters counters,
                         @Value("${dailyseed.draw.max-per-day:0}") int maxDrawsPerDay,
                         @Value("${dailyseed.session.cookie.enabled:true}") boolean cookieEnabled,
                         @Value("${dailyseed.session.cookie.secure:false}") boolean cookieSecure,
                         @Value("${dailyseed.dev-mode:false}") boolean devMode) {
        this.jdbc = jdbc;
        this.dataSource = dataSource;
        this.flyway = flyway;
        this.counters = counters;
        this.maxDrawsPerDay = maxDrawsPerDay;
        this.cookieEnabled = cookieEnabled;
        this.cookieSecure = cookieSecure;
        this.devMode = devMode;
    }

    // ==================== 响应形状 ====================

    public record Check(String name, boolean ok, String detail) {
    }

    public record Config(
            /** 0 = 无限重抽（开发期语义） */
            int drawMaxPerDay,
            boolean unlimitedDraws,
            boolean devModeAcknowledged,
            boolean sessionCookie,
            boolean sessionCookieSecure
    ) {
    }

    public record Report(
            boolean ok,
            String startedAt,
            long uptimeSeconds,
            String today,
            Config config,
            /** 配置风险：**看得见，但拦不住启动**。见 {@link #configCheck} 的注释 */
            List<String> warnings,
            List<Check> checks,
            ActivityCounters.Snapshot activity
    ) {
    }

    // ==================== 探测 ====================

    public Report report() {
        List<Check> checks = new ArrayList<>();
        List<String> warnings = new ArrayList<>();

        checks.add(migrationCheck());
        checks.add(databaseCheck());
        checks.add(cardSeedCheck());
        checks.add(clockCheck());
        checks.add(cookieCheck());

        // 配置风险只进 warnings，不进 ok：它是「该不该上线」，不是「能不能接流量」。
        // 混在一起的代价实测过——本地开发机（已承认开发模式）会被判 503，编排系统于是
        // 拒绝把流量打给一台其实完全正常的机器。
        warnings.addAll(configWarnings());

        boolean ok = checks.stream().allMatch(Check::ok);
        lastFailure.set(ok ? null : checks.stream()
                .filter(c -> !c.ok())
                .map(c -> c.name() + ": " + c.detail())
                .findFirst()
                .orElse(null));

        return new Report(
                ok,
                startedAt.toString(),
                Duration.between(startedAt, Instant.now()).toSeconds(),
                LocalDate.now(ZoneId.of("Asia/Shanghai")).toString(),
                new Config(maxDrawsPerDay, maxDrawsPerDay <= 0, devMode, cookieEnabled, cookieSecure),
                List.copyOf(warnings),
                checks,
                counters.snapshot());
    }

    /** 进程活着、但某些探测没过时的原因（日志用它，省得每次都要人肉重跑一遍） */
    public String lastFailure() {
        return lastFailure.get();
    }

    // ==================== 各项检查 ====================

    /**
     * 迁移到位没有。
     *
     * <p>这条抓的是一类很难查的事故：**表结构是新的、代码是旧的**（或者反过来）。
     * 手工改过库、或者迁移脚本被跳过的时候都会这样，而症状通常是运行期某个 SQL 报"未知列"，
     * 离真正的原因很远。
     */
    private Check migrationCheck() {
        try {
            MigrationInfo current = flyway.info().current();
            if (current == null) {
                return new Check("flyway", false, "库里没有任何迁移记录（Flyway 没跑？）");
            }
            return new Check("flyway", true, current.getVersion() + " " + current.getDescription());
        } catch (RuntimeException e) {
            return new Check("flyway", false, "读迁移状态失败：" + e.getClass().getSimpleName());
        }
    }

    /** 库连得上、连接池拿得到连接 */
    private Check databaseCheck() {
        try (var conn = dataSource.getConnection()) {
            boolean valid = conn.isValid(2);
            return new Check("database", valid,
                    valid ? "连接可用 · " + conn.getMetaData().getDatabaseProductVersion() : "连接无效");
        } catch (Exception e) {
            return new Check("database", false, e.getClass().getSimpleName() + ": " + e.getMessage());
        }
    }

    /** 种子灌进去了没有。空库是"能启动、但打开就 500"的经典死法，必须提前报出来 */
    private Check cardSeedCheck() {
        try {
            Integer cards = jdbc.sql("SELECT COUNT(*) FROM cards WHERE status = 'ACTIVE'")
                    .query(Integer.class).single();
            int n = cards == null ? 0 : cards;
            boolean ok = n >= MIN_CARDS;
            String detail = n + " 张可用卡" + (n == EXPECTED_CARDS ? "" : "（预期 " + EXPECTED_CARDS + "，可能改过卡片库）");
            return new Check("cardSeed", ok, detail);
        } catch (Exception e) {
            return new Check("cardSeed", false, "查卡片数失败：" + e.getClass().getSimpleName());
        }
    }

    /**
     * 「今天」算对没有。
     *
     * <p>这个产品整个建立在一个日期上（每天一粒、一天一行、补留窗口 3 天），
     * 而"今天是哪天"是按用户时区算的。**库的时区、JVM 的时区、用户的时区**三者不一致时，
     * 症状是"半夜之后领到的是昨天的卡"——这种 bug 平时看不出来，只在跨零点那几个小时出现。
     * 所以这里把三者并排报出来，让人一眼能对。
     */
    private Check clockCheck() {
        try {
            String dbZone = jdbc.sql("SELECT @@session.time_zone").query(String.class).single();
            String now = jdbc.sql("SELECT NOW(6)").query(String.class).single();
            LocalDate appToday = LocalDate.now(ZoneId.of("Asia/Shanghai"));
            // 库和应用跨了零点时不一定是谁错了，所以这条只把三者并排报出来，不判失败
            //（默认用户时区就是 Asia/Shanghai；真出现偏差时应该改 timezone，而不是改这里）
            return new Check("clock", true, "JVM=" + ZoneId.systemDefault()
                    + " · MySQL=" + dbZone
                    + " · 应用今天=" + appToday
                    + " · 库现在=" + now);
        } catch (Exception e) {
            return new Check("clock", false, "读库时间失败：" + e.getClass().getSimpleName());
        }
    }

    /**
     * 配置风险——**只出 warnings，绝不影响 {@code ok}**。
     *
     * <p>这条界是踩过一次才划清的：最初把"无限重抽 / 非 secure Cookie"判成健康检查失败，
     * 于是**本地开发机**（明确承认了 {@code DAILYSEED_DEV_MODE=true}）返回 503。
     * 那是个设计错——编排系统看到 503 会拒绝把流量打给一台其实是好的机器。
     *
     * <p>正确的分工：
     * <ul>
     *   <li><b>ready（影响 ok/503）</b>：库连得上吗、迁移跑完了吗、种子灌进去了吗——
     *       这些不过，服务确实没法用</li>
     *   <li><b>warnings（不影响 ok）</b>：这台机器是不是"能公开见人"的样子——
     *       它是**部署判断**，不是**存活判断**。真正会拦启动的是 {@code StartupGuard}</li>
     * </ul>
     */
    private List<String> configWarnings() {
        List<String> warnings = new ArrayList<>();
        if (maxDrawsPerDay <= 0) {
            warnings.add(devMode
                    ? "抽卡配额=无限（已确认为开发模式，上线前要改回 1）"
                    : "抽卡配额=无限，但**没有**承认开发模式——正常情况下 StartupGuard 会拦住这个组合");
        }
        if (cookieEnabled && !cookieSecure) {
            warnings.add(devMode
                    ? "身份 Cookie 没有 secure（本地 http 可以，https 上必须开）"
                    : "身份 Cookie 没有 secure：https 下浏览器可能直接丢弃它，清缓存找回那条退路会静默失效");
        }
        if (!cookieEnabled) {
            warnings.add("身份 Cookie 已关闭：清掉 localStorage 之后没有任何退路，只能靠同步码");
        }
        return warnings;
    }

    /**
     * 身份退路配得自不自洽——这一段最容易配错，所以**它影响 ok**。
     *
     * <p>HttpOnly Cookie 的存在理由只有一个："用户清掉 localStorage 之后还能被认回来"。
     * 如果配成"开着但不 secure 又处在生产模式"，浏览器（https 下）可能直接丢弃它，
     * 于是那条退路**形同不存在**——而它失效时是静默的，没有任何人会来报错。
     * 这种"以为有、其实没有"的状态必须报出来。
     */
    private Check cookieCheck() {
        if (!cookieEnabled) {
            return new Check("sessionCookie", true, "已关闭——身份退路不存在，只能靠同步码");
        }
        // 本地开发（明确承认开发模式）允许非 secure：localhost 是安全上下文
        boolean ok = cookieSecure || devMode;
        return new Check("sessionCookie", ok, ok
                ? (cookieSecure ? "开启且 secure" : "开启（本地开发，非 secure）")
                : "开启了但**没有** secure，又不在开发模式：https 下这条 Cookie 可能被丢弃，退路形同不存在");
    }
}
