package com.dailyseed.user;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.LocalTime;
import java.util.HexFormat;
import java.util.Optional;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

/** 匿名 ID + 8 位同步码（零注册，设计文档 §7）。 */
@Repository
public class UserStore {

    /** 同步码只显示一次，之后服务端只留哈希 */
    public record Session(long userId, String syncCode) {
    }

    /**
     * 同步码换发的结果。
     *
     * <p>{@code syncCode} 是**新码的明文**，同样只有这一次机会能看到（库里只存哈希）——
     * 换发同时让旧码作废，所以取值失败时整个事务都得回滚，不能让用户卡在"旧码废了、新码没拿到"。
     */
    public record Restored(long userId, String syncCode) {
    }

    /** 用户自设的提醒偏好（生成 .ics 用）；没设过时间就是 null，由调用方给默认值 */
    public record ReminderPreference(String timezone, LocalTime remindAt) {
        public ReminderPreference {
            timezone = timezone == null ? DEFAULT_TIMEZONE : timezone;
        }
    }

    public static final String DEFAULT_TIMEZONE = "Asia/Shanghai";

    /** 去掉易混淆字符 0/O、1/I/L */
    private static final char[] ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ".toCharArray();

    private final JdbcClient jdbc;
    private final SecureRandom random = new SecureRandom();

    public UserStore(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    @Transactional
    public Session createAnonymous(String deviceId) {
        long userId = insertUser();
        jdbc.sql("INSERT INTO user_devices (user_id, device_id) VALUES (:u, :d)")
                .param("u", userId)
                .param("d", deviceId)
                .update();
        return new Session(userId, replaceSyncCode(userId));
    }

    /**
     * 用同步码换一个身份（设计文档 §7.2）。
     *
     * <p>服务端**只存哈希**，所以查得到就说明码是对的——不需要额外的比对步骤，
     * 这也意味着码本身就是唯一凭据，拿到哈希行的唯一途径就是提交正确的码。
     *
     * <p>成功时：① 把设备改绑到这个 user ② <b>换发新码</b>并让旧码立即失效（§7.2「可重置」）。
     * 换发是为了救"码抄错一半"的人，也让换手机这件事有个干净的收尾。
     * ②与③必须同一个事务：取值失败就整个回滚，绝不能留下"旧码作废、新码没给"的用户。
     */
    @Transactional
    public Optional<Restored> restoreBySyncCode(String syncCode, String deviceId) {
        Optional<Long> userId = findUserIdBySyncCodeHash(sha256(syncCode));
        if (userId.isEmpty()) {
            return Optional.empty();
        }
        rebindDevice(userId.get(), deviceId);
        return Optional.of(new Restored(userId.get(), replaceSyncCode(userId.get())));
    }

    /** 同步码哈希 → userId。恢复接口的全部凭据判定就压在这一条查询上。 */
    public Optional<Long> findUserIdBySyncCodeHash(String syncCodeHash) {
        return jdbc.sql("SELECT id FROM users WHERE sync_code_hash = :hash")
                .param("hash", syncCodeHash)
                .query(Long.class)
                .optional();
    }

    /**
     * 把设备改绑到另一个 user。
     *
     * <p>先删再插，不写成两条分支：{@code device_id} 上有唯一键，先删掉旧绑定才插得进去；
     * 而"这台设备本来就绑在这个 user 上"时删掉再插回去也是同一个结果，不值得多一条路径。
     */
    private void rebindDevice(long userId, String deviceId) {
        jdbc.sql("DELETE FROM user_devices WHERE device_id = :d").param("d", deviceId).update();
        jdbc.sql("INSERT INTO user_devices (user_id, device_id) VALUES (:u, :d)")
                .param("u", userId)
                .param("d", deviceId)
                .update();
    }

    /**
     * 生成一个新同步码并落库，返回**明文**（只有这一次机会能看到）。
     *
     * <p>新建用户和换发新码走的是同一条路：写入时机不同，但"库里的哈希指向哪个明文"
     * 这件事只有一处代码负责，就不会出现两条路径写法不一致的漏子。
     */
    private String replaceSyncCode(long userId) {
        String syncCode = newSyncCode();
        jdbc.sql("UPDATE users SET sync_code_hash = :hash WHERE id = :id")
                .param("hash", sha256(syncCode))
                .param("id", userId)
                .update();
        return syncCode;
    }

    public Optional<Long> findUserIdByDevice(String deviceId) {
        return jdbc.sql("SELECT user_id FROM user_devices WHERE device_id = :d")
                .param("d", deviceId)
                .query(Long.class)
                .optional();
    }

    /** 这个人现在挂着几台设备（有两条以上说明他手上不止一台，Cookie 自愈就不该另起炉灶） */
    public int countDevices(long userId) {
        Integer n = jdbc.sql("SELECT COUNT(*) FROM user_devices WHERE user_id = :u")
                .param("u", userId)
                .query(Integer.class)
                .single();
        return n == null ? 0 : n;
    }

    /** 把一台"没被注册过"的设备记到这个人名下（Cookie 自愈用） */
    public void attachDevice(long userId, String deviceId) {
        jdbc.sql("INSERT INTO user_devices (user_id, device_id) VALUES (:u, :d)")
                .param("u", userId)
                .param("d", deviceId)
                .update();
    }

    /** 「今天」按用户所在时区算，不按服务器时区 */
    public String timezone(long userId) {
        return jdbc.sql("SELECT timezone FROM users WHERE id = :id")
                .param("id", userId)
                .query(String.class)
                .optional()
                .orElse(DEFAULT_TIMEZONE);
    }

    /** 生成 .ics 需要的两样东西：时区 + 用户自设的提醒时间 */
    public Optional<ReminderPreference> reminderPreference(long userId) {
        return jdbc.sql("SELECT timezone, remind_at FROM users WHERE id = :id")
                .param("id", userId)
                .query((rs, i) -> new ReminderPreference(
                        rs.getString("timezone"),
                        rs.getObject("remind_at", LocalTime.class)))
                .optional();
    }

    /** 用户什么时候想被提醒。下一次下载 .ics 才会用上，所以这里不返回任何东西 */
    public void updateRemindAt(long userId, LocalTime remindAt) {
        jdbc.sql("UPDATE users SET remind_at = :t WHERE id = :id")
                .param("t", remindAt)
                .param("id", userId)
                .update();
    }

    /** 建一个匿名用户（同步码稍后由 {@link #replaceSyncCode} 落库），返回自增主键 */
    private long insertUser() {
        KeyHolder keys = new GeneratedKeyHolder();
        jdbc.sql("INSERT INTO users (sync_code_hash) VALUES (:hash)")
                .param("hash", sha256(newSyncCode()))
                .update(keys, "id");
        Number generated = keys.getKey();
        if (generated == null) {
            throw new IllegalStateException("用户创建后拿不到自增主键");
        }
        return generated.longValue();
    }

    private String newSyncCode() {
        StringBuilder sb = new StringBuilder(9);
        for (int i = 0; i < 8; i++) {
            if (i == 4) {
                sb.append('-');
            }
            sb.append(ALPHABET[random.nextInt(ALPHABET.length)]);
        }
        return sb.toString();
    }

    static String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 不可用", e);
        }
    }
}
